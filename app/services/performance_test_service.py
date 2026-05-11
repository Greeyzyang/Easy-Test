import asyncio
import httpx
import json
import time
import random
import statistics
import copy
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PerformanceTest, PerformanceTestReport, Interface, Variable
from app.schemas.base_schemas import TestStatus
from app.utils.execution_context import BaseExecutionContext
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RequestResult:
    response_time_ms: float
    status_code: int
    is_error: bool
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)
    response_body: Optional[Dict] = None
    response_headers: Optional[Dict] = None


@dataclass
class ScenarioStats:
    name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0

    @property
    def avg_response_time(self) -> float:
        return self.total_response_time / self.total_requests if self.total_requests > 0 else 0.0


class WorkerContext(BaseExecutionContext):
    """压测 worker 专用上下文，继承 BaseExecutionContext"""

    def set_runtime_variables(self, vars_dict: Dict[str, Any]):
        for key, value in vars_dict.items():
            self.variables[f"user_{key}"] = value
            self.variables[key] = value

    def remove_runtime_variables(self, vars_dict: Dict[str, Any]):
        for key in vars_dict.keys():
            self.variables.pop(f"user_{key}", None)
            self.variables.pop(key, None)


class UserPool:
    def __init__(self, users: List[Dict], mode: str = "random"):
        self.users = users
        self.mode = mode
        self._index = 0

    def select(self) -> Optional[Dict]:
        if not self.users:
            return None
        if self.mode == "round_robin":
            user = self.users[self._index % len(self.users)]
            self._index += 1
            return user
        else:
            return random.choice(self.users)


class MetricsAggregator:
    def __init__(self):
        self._lock = threading.Lock()
        self._response_times: List[float] = []
        self._success_count: int = 0
        self._error_count: int = 0
        self._scenario_stats: Dict[str, ScenarioStats] = {}
        self._request_count: int = 0
        self._start_time: float = time.time()
        self._timeline: List[Dict] = []

    def record(self, result: RequestResult, scenario_name: str = "default"):
        with self._lock:
            self._response_times.append(result.response_time_ms)
            self._request_count += 1
            if result.is_error:
                self._error_count += 1
            else:
                self._success_count += 1

            if scenario_name not in self._scenario_stats:
                self._scenario_stats[scenario_name] = ScenarioStats(name=scenario_name)
            s = self._scenario_stats[scenario_name]
            s.total_requests += 1
            s.total_response_time += result.response_time_ms
            if result.is_error:
                s.failed_requests += 1
            else:
                s.successful_requests += 1

    def get_total_requests(self) -> int:
        with self._lock:
            return self._request_count

    def get_percentile(self, p: float) -> float:
        with self._lock:
            rt_list = list(self._response_times)
        if not rt_list:
            return 0.0
        try:
            return float(statistics.quantiles(sorted(rt_list), n=100)[int(p * 100) - 1])
        except (IndexError, ValueError):
            return 0.0

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = self._success_count + self._error_count
            elapsed = time.time() - self._start_time
            rt_list = list(self._response_times)
            return {
                "total_requests": total,
                "successful_requests": self._success_count,
                "failed_requests": self._error_count,
                "error_rate": round(self._error_count / total, 4) if total > 0 else 0.0,
                "avg_response_time": round(statistics.mean(rt_list), 2) if rt_list else 0.0,
                "min_response_time": round(min(rt_list), 2) if rt_list else 0.0,
                "max_response_time": round(max(rt_list), 2) if rt_list else 0.0,
                "median_response_time": round(statistics.median(rt_list), 2) if rt_list else 0.0,
                "p90_response_time": round(self.get_percentile(0.90), 2),
                "p95_response_time": round(self.get_percentile(0.95), 2),
                "p99_response_time": round(self.get_percentile(0.99), 2),
                "stddev_response_time": round(statistics.stdev(rt_list), 2) if len(rt_list) > 1 else 0.0,
                "requests_per_second": round(total / elapsed, 2) if elapsed > 0 else 0.0,
            }

    def take_timeline_snapshot(self) -> Dict:
        with self._lock:
            total = self._success_count + self._error_count
            elapsed = time.time() - self._start_time
            rt_list = list(self._response_times)
            point = {
                "elapsed_seconds": round(elapsed, 1),
                "total_requests": total,
                "successful_requests": self._success_count,
                "failed_requests": self._error_count,
                "avg_response_time": round(statistics.mean(rt_list), 2) if rt_list else 0.0,
                "requests_per_second": round(total / elapsed, 2) if elapsed > 0 else 0.0,
            }
            self._timeline.append(point)
            return point

    def get_timeline(self) -> List[Dict]:
        with self._lock:
            return list(self._timeline)

    def get_scenario_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                name: {
                    "total_requests": s.total_requests,
                    "successful_requests": s.successful_requests,
                    "failed_requests": s.failed_requests,
                    "avg_response_time": round(s.avg_response_time, 2),
                }
                for name, s in self._scenario_stats.items()
            }


class PerformanceTestWorker:
    def __init__(
        self,
        worker_id: int,
        httpx_client: httpx.AsyncClient,
        scenario: Dict,
        base_url: str,
        headers: Dict[str, str],
        aggregator: MetricsAggregator,
        stop_event: asyncio.Event,
        user_pool: Optional[UserPool],
        auth_config: Optional[Dict],
        global_variables: Optional[Dict] = None,
        total_requests_limit: Optional[int] = None,
    ):
        self.worker_id = worker_id
        self.client = httpx_client
        self.scenario = scenario
        self.base_url = base_url
        self.headers = headers
        self.aggregator = aggregator
        self.stop_event = stop_event
        self.user_pool = user_pool
        self.auth_config = auth_config or {}
        self.global_variables = global_variables or {}
        self.total_requests_limit = total_requests_limit
        self._auth_token: Optional[str] = None
        self._auth_headers: Dict[str, str] = {}
        self._current_user: Optional[Dict] = None
        self._context = WorkerContext()
        self._context.variables.update(self.global_variables)

    def _get_scenario(self) -> Optional[Dict]:
        if self.scenario.get("enabled", True):
            return self.scenario
        return None

    async def _authenticate(self, user: Dict) -> Optional[str]:
        login_url = self.auth_config.get("login_url", "")
        if not login_url:
            return None
        try:
            body = self.auth_config.get("login_body_template", {})
            body = await self._context.process_template_dict(body)
            body = {k: (v if v != "${username}" else user.get("username", "")
                     if isinstance(v, str) else v) for k, v in body.items()}
            body = {k: (v if v != "${password}" else user.get("password", "")
                     if isinstance(v, str) else v) for k, v in body.items()}

            url = login_url if login_url.startswith("http") else f"{self.base_url.rstrip('/')}/{login_url.lstrip('/')}"
            resp = await self.client.post(url, json=body, timeout=10.0)

            if resp.status_code == 200:
                data = resp.json()
                token_key = self.auth_config.get("token_key", "access_token")
                for key in [token_key, "token", "access_token"]:
                    if key in data:
                        return str(data[key])
                logger.warning(f"Login succeeded but no token found in response: {list(data.keys())}")
            else:
                logger.warning(f"Login failed for user {user.get('username')}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Authentication error: {e}")
        return None

    async def _extract_step_variables(self, step: Dict):
        extract_configs = step.get("extract_variables", [])
        if not extract_configs:
            return
        for cfg in extract_configs:
            var_name = cfg.get("name")
            if var_name:
                await self._context.extract_variable(var_name, cfg)

    async def _execute_step(self, step: Dict) -> RequestResult:
        step_headers = dict(self.headers)
        step_headers.update(self._auth_headers)
        step_headers.update(step.get("override_headers") or {})

        override_url = step.get("override_url") or ""
        override_method = step.get("override_method", "GET").upper()
        override_body = step.get("override_body") or {}

        processed_url = await self._context.process_template_string(override_url)
        if not processed_url.startswith("http"):
            processed_url = f"{self.base_url.rstrip('/')}/{processed_url.lstrip('/')}"

        processed_headers = await self._context.process_template_dict(step_headers)
        processed_body = await self._context.process_template_dict(copy.deepcopy(override_body))
        self._context.last_request_body = processed_body or {}

        try:
            req_headers = {k: str(v) for k, v in processed_headers.items() if v is not None}
            req_start = time.perf_counter()

            if processed_body:
                response = await self.client.request(
                    override_method,
                    processed_url,
                    json=processed_body,
                    headers=req_headers,
                    timeout=30.0,
                )
            else:
                response = await self.client.request(
                    override_method,
                    processed_url,
                    headers=req_headers,
                    timeout=30.0,
                )

            rt_ms = (time.perf_counter() - req_start) * 1000

            resp_body = {}
            try:
                resp_body = response.json()
            except Exception:
                resp_body = {"_raw_text": response.text}

            self._context.update_response(
                body=resp_body,
                headers=dict(response.headers),
                cookies=response.cookies,
            )

            result = RequestResult(
                response_time_ms=rt_ms,
                status_code=response.status_code,
                is_error=response.status_code >= 400,
                error_message="" if response.status_code < 400 else f"HTTP {response.status_code}",
                response_body=resp_body,
                response_headers=dict(response.headers),
            )

            await self._extract_step_variables(step)

            return result

        except httpx.TimeoutException:
            return RequestResult(
                response_time_ms=30000, status_code=0,
                is_error=True, error_message="Request timeout (30s)",
            )
        except httpx.RequestError as e:
            return RequestResult(
                response_time_ms=0, status_code=0,
                is_error=True, error_message=f"Request error: {str(e)}",
            )
        except Exception as e:
            return RequestResult(
                response_time_ms=0, status_code=0,
                is_error=True, error_message=str(e),
            )

    async def run(self):
        while not self.stop_event.is_set():
            if self.total_requests_limit is not None:
                if self.aggregator.get_total_requests() >= self.total_requests_limit:
                    break

            user = self.user_pool.select() if self.user_pool else None

            if user:
                self._context.set_runtime_variables(user)
                # 用户换了就重新登录
                if user != self._current_user or not self._auth_token:
                    self._current_user = user
                    self._auth_token = await self._authenticate(user)
                    if self._auth_token:
                        self._auth_headers = {"X-Auth-Token": self._auth_token}
                    else:
                        self._auth_headers = {}
            else:
                self._context.remove_runtime_variables(user or {})

            scenario = self._get_scenario()
            if not scenario:
                await asyncio.sleep(0.5)
                continue

            steps = scenario.get("steps", [])
            scenario_name = scenario.get("name", "unknown")

            for step in steps:
                if self.stop_event.is_set():
                    break
                if self.total_requests_limit is not None:
                    if self.aggregator.get_total_requests() >= self.total_requests_limit:
                        self.stop_event.set()
                        break

                result = await self._execute_step(step)
                self.aggregator.record(result, scenario_name)

                think_ms = step.get("think_time_ms", 0)
                if think_ms > 0:
                    await asyncio.sleep(think_ms / 1000.0)
                else:
                    await asyncio.sleep(random.uniform(0.05, 0.2))

            scenario_delay_ms = scenario.get("scenario_delay_ms", 0)
            if scenario_delay_ms > 0 and not self.stop_event.is_set():
                await asyncio.sleep(scenario_delay_ms / 1000.0)


class PerformanceTestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_performance_test(self, performance_test_id: str) -> PerformanceTest:
        result = await self.db.execute(
            select(PerformanceTest).where(PerformanceTest.id == performance_test_id)
        )
        pt = result.scalar_one_or_none()
        if not pt:
            raise ValueError(f"PerformanceTest {performance_test_id} not found")
        return pt

    async def _load_interfaces(self, interface_ids: List[str]) -> Dict[str, Interface]:
        if not interface_ids:
            return {}
        result = await self.db.execute(
            select(Interface).where(Interface.id.in_(interface_ids))
        )
        return {i.id: i for i in result.scalars().all()}

    async def _load_user_pool(self, var_name: str) -> List[Dict]:
        if not var_name:
            return []
        result = await self.db.execute(select(Variable).where(Variable.key == var_name))
        var = result.scalar_one_or_none()
        if not var:
            logger.warning(f"User pool variable '{var_name}' not found in database")
            return []
        try:
            value = var.value
            if isinstance(value, str):
                users = json.loads(value)
            else:
                users = value
            if isinstance(users, list):
                return users
            logger.warning(f"User pool '{var_name}' is not a list: {type(users)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse user pool '{var_name}': {e}")
        return []

    async def _load_global_variables(self, project_id: str) -> Dict[str, Any]:
        from app.models import Variable
        result = await self.db.execute(
            select(Variable)
        )
        variables = {}
        for var in result.scalars().all():
            try:
                if isinstance(var.value, str):
                    try:
                        variables[var.key] = json.loads(var.value)
                    except json.JSONDecodeError:
                        variables[var.key] = var.value
                else:
                    variables[var.key] = var.value
            except Exception as e:
                logger.warning(f"Failed to parse variable '{var.key}': {e}")
                variables[var.key] = var.value
        return variables

    def _build_scenario(self, scenario_data: Dict, interfaces: Dict[str, Interface]) -> Dict:
        steps_data = []
        for step in scenario_data.get("steps", []):
            interface_id = step.get("interface_id")
            if interface_id and interface_id in interfaces:
                iface = interfaces[interface_id]
                steps_data.append({
                    "name": step.get("name", iface.name),
                    "override_url": iface.url,
                    "override_method": iface.method,
                    "override_headers": iface.headers or {},
                    "override_body": iface.body or {},
                    "think_time_ms": step.get("think_time_ms", 0),
                    "extract_variables": step.get("extract_variables", []),
                })
            else:
                steps_data.append({
                    "name": step.get("name", "custom"),
                    "override_url": step.get("override_url", ""),
                    "override_method": step.get("override_method", "GET"),
                    "override_headers": step.get("override_headers", {}),
                    "override_body": step.get("override_body", {}),
                    "think_time_ms": step.get("think_time_ms", 0),
                    "extract_variables": step.get("extract_variables", []),
                })
        return {
            "name": scenario_data.get("name", "scenario"),
            "enabled": scenario_data.get("enabled", True),
            "scenario_delay_ms": scenario_data.get("scenario_delay_ms", 0),
            "steps": steps_data,
        }

    async def run_performance_test(
        self,
        performance_test_id: str,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> PerformanceTestReport:
        pt = await self._load_performance_test(performance_test_id)
        request_config = pt.request_config or {}
        scenario_raw = request_config.get("scenario")
        if not scenario_raw:
            raise ValueError("Performance test has no scenario configured")

        interface_ids = [
            s.get("interface_id")
            for s in scenario_raw.get("steps", [])
            if s.get("interface_id")
        ]
        interfaces = await self._load_interfaces(interface_ids)
        base_url = pt.target_base_url or ""
        scenario = self._build_scenario(scenario_raw, interfaces)

        for step in scenario.get("steps", []):
            if not step["override_url"]:
                raise ValueError(f"Step '{step['name']}' has no URL configured")

        global_variables = await self._load_global_variables(pt.project_id)
        logger.info(f"Loaded {len(global_variables)} global variables")

        if base_url:
            global_variables["base_url"] = base_url

        user_pool = None
        auth_config = (request_config or {}).get("user_pool_auth_config") or {}
        if pt.user_pool_ref:
            users = await self._load_user_pool(pt.user_pool_ref)
            if users:
                user_pool = UserPool(users, pt.user_pool_mode or "random")
                logger.info(f"Loaded user pool '{pt.user_pool_ref}' with {len(users)} users, mode={pt.user_pool_mode}")
            else:
                logger.warning(f"User pool '{pt.user_pool_ref}' is empty or not found")

        report = PerformanceTestReport(
            performance_test_id=performance_test_id,
            status=TestStatus.IN_PROGRESS,
            start_time=datetime.utcnow(),
        )
        self.db.add(report)
        await self.db.flush()

        pt.status = TestStatus.IN_PROGRESS
        await self.db.flush()

        aggregator = MetricsAggregator()
        stop_event = asyncio.Event()

        run_mode = getattr(pt, "run_mode", "duration") or "duration"
        total_requests_limit = getattr(pt, "total_requests_limit", None)
        if run_mode == "fixed_requests" and not total_requests_limit:
            total_requests_limit = (pt.concurrent_users or 10) * (pt.duration_seconds or 60)

        httpx_client = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=pt.concurrent_users * 2,
                max_keepalive_connections=50
            ),
        )

        try:
            workers = [
                PerformanceTestWorker(
                    worker_id=i,
                    httpx_client=httpx_client,
                    scenario=scenario,
                    base_url=base_url,
                    headers={},
                    aggregator=aggregator,
                    stop_event=stop_event,
                    user_pool=user_pool,
                    auth_config=auth_config,
                    global_variables=global_variables,
                    total_requests_limit=total_requests_limit if run_mode == "fixed_requests" else None,
                )
                for i in range(pt.concurrent_users)
            ]

            active_workers = [asyncio.create_task(w.run()) for w in workers]

            start_time = time.time()
            duration = pt.duration_seconds or 60
            snapshot_interval = 2.0
            last_snapshot = start_time
            aggregator.take_timeline_snapshot()

            if run_mode == "duration":
                while time.time() - start_time < duration:
                    await asyncio.sleep(1.0)
                    if time.time() - last_snapshot >= snapshot_interval:
                        aggregator.take_timeline_snapshot()
                        snapshot = aggregator.get_snapshot()
                        last_snapshot = time.time()
                        if progress_callback:
                            await progress_callback(
                                report_id=report.id,
                                status="PROGRESS",
                                progress=int((time.time() - start_time) / duration * 100),
                                text=f"Running: {snapshot['total_requests']} reqs, "
                                f"Avg RT: {snapshot['avg_response_time']:.0f}ms, "
                                f"RPS: {snapshot['requests_per_second']:.1f}",
                                **snapshot,
                            )
            else:
                target = total_requests_limit or 1
                while aggregator.get_total_requests() < target:
                    await asyncio.sleep(1.0)
                    if time.time() - last_snapshot >= snapshot_interval:
                        aggregator.take_timeline_snapshot()
                        snapshot = aggregator.get_snapshot()
                        last_snapshot = time.time()
                        done = min(100, int(aggregator.get_total_requests() / target * 100))
                        if progress_callback:
                            await progress_callback(
                                report_id=report.id,
                                status="PROGRESS",
                                progress=done,
                                text=f"Requests: {snapshot['total_requests']}/{target}, "
                                f"Avg RT: {snapshot['avg_response_time']:.0f}ms, "
                                f"RPS: {snapshot['requests_per_second']:.1f}",
                                **snapshot,
                            )

            stop_event.set()
            await asyncio.gather(*active_workers, return_exceptions=True)

        finally:
            await httpx_client.aclose()

        end_time = datetime.utcnow()
        final_snapshot = aggregator.get_snapshot()

        report.status = TestStatus.COMPLETED if final_snapshot["error_rate"] < 1.0 else TestStatus.FAILED
        report.end_time = end_time
        report.duration_seconds = int(time.time() - start_time)
        report.total_requests = final_snapshot["total_requests"]
        report.successful_requests = final_snapshot["successful_requests"]
        report.failed_requests = final_snapshot["failed_requests"]
        report.error_rate = final_snapshot["error_rate"]
        report.avg_response_time = final_snapshot["avg_response_time"]
        report.min_response_time = final_snapshot["min_response_time"]
        report.max_response_time = final_snapshot["max_response_time"]
        report.median_response_time = final_snapshot["median_response_time"]
        report.p90_response_time = final_snapshot["p90_response_time"]
        report.p95_response_time = final_snapshot["p95_response_time"]
        report.p99_response_time = final_snapshot["p99_response_time"]
        report.stddev_response_time = final_snapshot["stddev_response_time"]
        report.requests_per_second = final_snapshot["requests_per_second"]
        report.timeline_data = aggregator.get_timeline()
        report.scenario_stats = aggregator.get_scenario_stats()

        pt.status = report.status
        await self.db.flush()

        if progress_callback:
            final_data = aggregator.get_snapshot()
            final_data["report_id"] = report.id
            await progress_callback(
                report_id=report.id,
                status="SUCCESS",
                progress=100,
                text="Performance test completed",
                **final_data,
            )

        logger.info(
            f"Performance test {performance_test_id} completed: "
            f"{report.total_requests} requests, "
            f"RPS: {report.requests_per_second}, "
            f"Avg RT: {report.avg_response_time}ms, "
            f"P99: {report.p99_response_time}ms"
        )
        return report
