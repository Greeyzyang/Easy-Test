from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

def generate_test_report_pdf(report_data: dict) -> bytes:
    """生成测试报告PDF
    
    Args:
        report_data: 测试报告数据
        
    Returns:
        bytes: PDF文件内容
    """
    # 创建内存文件对象
    buffer = io.BytesIO()
    
    # 创建PDF文档
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # 获取样式
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12
    )
    
    # 构建文档内容
    elements = []
    
    # 标题
    elements.append(Paragraph(f"测试报告: {report_data['name']}", title_style))
    elements.append(Spacer(1, 12))
    
    # 基本信息
    elements.append(Paragraph("基本信息", heading_style))
    basic_info = [
        ["报告ID", report_data['id']],
        ["测试套件", report_data['suite_name']],
        ["执行状态", report_data['status']],
        ["总耗时", f"{report_data['duration']}秒"]
    ]
    basic_table = Table(basic_info, colWidths=[2*inch, 4*inch])
    basic_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(basic_table)
    elements.append(Spacer(1, 20))
    
    # 测试结果统计
    elements.append(Paragraph("测试结果统计", heading_style))
    stats_info = [
        ["总用例数", str(report_data['total_cases'])],
        ["成功用例", str(report_data['success_cases'])],
        ["失败用例", str(report_data['failed_cases'])],
        ["跳过用例", str(report_data['skipped_cases'])]
    ]
    stats_table = Table(stats_info, colWidths=[2*inch, 4*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 20))
    
    # 测试用例详情
    elements.append(Paragraph("测试用例详情", heading_style))
    case_data = []
    case_data.append(["用例名称", "步骤名称", "状态", "耗时(秒)", "错误信息"])

    for case in report_data['case_results']:
        for step in case.get('steps', []):
            if str(step.get('status', '')).lower() != 'passed' and step.get('error_message'):
                case_data.append([
                    case['name'],
                    step.get('step_name', ''),
                    step.get('status', ''),
                    str(step.get('duration', '')),
                    step.get('error_message', '')
                ])

    case_table = Table(case_data, colWidths=[2.5*inch, 2*inch, 1*inch, 1*inch, 2*inch])
    case_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(case_table)
    
    # 生成PDF
    doc.build(elements)
    
    # 获取PDF内容
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content 