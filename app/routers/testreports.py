from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.testreport_service import TestreportService
from app.utils.response import create_response, ResponseModel
from fastapi.responses import StreamingResponse
import io
from app.schemas.testreport import TestreportDetail, TestreportRead
from app.schemas.base_schemas import PaginationParams
from typing import List
from app.schemas.testreport import TestStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rest/v1/testreports", tags=["testreports"])

@router.get("/{report_id}/", response_model=ResponseModel)
async def get_testreport(report_id: str, db: AsyncSession = Depends(get_db)):
    """获取测试报告详情"""
    logger.info(f"获取测试报告详情: {report_id}")
    service = TestreportService(db)
    report = await service._get_testreport(report_id)
    report_data = TestreportDetail.model_validate(report)
    return await create_response(data=report_data)

@router.get("/", response_model=ResponseModel)
async def get_testreports(
    params: PaginationParams = Depends(),
    status: TestStatus | None = Query(None, description="Filter by test report status"),
    project_id: str | None = Query(None, description="Filter by project ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取测试报告列表"""
    logger.info(f"获取测试报告列表: skip={params.skip}, limit={params.limit}, status={status}, project_id={project_id}")
    service = TestreportService(db)
    testreports, total = await service.list_reports(skip=params.skip, limit=params.limit, status=status, project_id=project_id)
    reports_data = [TestreportRead.model_validate(r) for r in testreports]
    return await create_response(data={"items": reports_data, "total": total})

@router.delete("/", response_model=ResponseModel)
async def delete_all_testreports(db: AsyncSession = Depends(get_db)):
    """删除所有测试报告"""
    logger.info("删除所有测试报告")
    service = TestreportService(db)
    await service.delete_all_reports()
    return await create_response(data=None, msg="所有测试报告删除成功")

@router.delete("/{report_id}/", response_model=ResponseModel)
async def delete_testreport(report_id: str, db: AsyncSession = Depends(get_db)):
    """删除测试报告"""
    logger.info(f"删除测试报告: {report_id}")
    service = TestreportService(db)
    await service.delete_report(report_id)
    return await create_response(data=None, msg=f"测试报告 {report_id} 删除成功")

@router.get("/{report_id}/export/")
async def export_testreport(report_id: str, db: AsyncSession = Depends(get_db)):
    """导出测试报告为PDF"""
    logger.info(f"导出测试报告为PDF: {report_id}")
    service = TestreportService(db)
    try:
        # 获取PDF文件内容
        pdf_content = await service.generate_pdf_report(report_id)
        
        # 创建内存文件对象
        pdf_file = io.BytesIO(pdf_content)
        
        # 设置文件名
        filename = f"test_report_{report_id}.pdf"
        
        # 返回文件流
        return StreamingResponse(
            pdf_file,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"导出PDF失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出PDF失败: {str(e)}")







