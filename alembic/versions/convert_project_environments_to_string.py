"""convert project environments to string

Revision ID: convert_project_environments_to_string
Revises: 1d1b7455a273
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import json

# revision identifiers, used by Alembic.
revision = 'convert_project_environments_to_string'
down_revision = '1d1b7455a273'
branch_labels = None
depends_on = None


def upgrade():
    # 获取项目表
    conn = op.get_bind()
    projects = conn.execute("SELECT id, environments FROM projects").fetchall()
    
    # 更新每个项目的environments字段
    for project in projects:
        if project.environments:
            # 将JSON格式转换为字符串格式
            env_dict = json.loads(project.environments)
            env_list = []
            for name, url in env_dict.items():
                env_list.append(f"{name}:{url}")
            new_env_str = ";".join(env_list)
            
            # 更新数据库
            conn.execute(
                "UPDATE projects SET environments = %s WHERE id = %s",
                (new_env_str, project.id)
            )

    # 修改字段类型
    op.alter_column('projects', 'environments',
                    existing_type=sa.JSON(),
                    type_=sa.String(1000),
                    existing_nullable=True)


def downgrade():
    # 获取项目表
    conn = op.get_bind()
    projects = conn.execute("SELECT id, environments FROM projects").fetchall()
    
    # 更新每个项目的environments字段
    for project in projects:
        if project.environments:
            # 将字符串格式转换回JSON格式
            env_dict = {}
            env_pairs = project.environments.split(';')
            for pair in env_pairs:
                if ':' in pair:
                    name, url = pair.split(':', 1)
                    env_dict[name] = url
            
            # 更新数据库
            conn.execute(
                "UPDATE projects SET environments = %s WHERE id = %s",
                (json.dumps(env_dict), project.id)
            )

    # 修改字段类型
    op.alter_column('projects', 'environments',
                    existing_type=sa.String(1000),
                    type_=sa.JSON(),
                    existing_nullable=True) 