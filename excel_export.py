"""Excel导出模块 - 将爬取数据导出为Excel文件"""
import json
import math
import os
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side


# 样式常量
HEADER_FONT = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
HEADER_FILL = PatternFill(patternType='solid', fgColor='4472C4')
HEADER_ALIGN = Alignment(horizontal='center', vertical='center')
CELL_FONT = Font(name='微软雅黑', size=10)
CELL_ALIGN = Alignment(vertical='center', wrap_text=True)
CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)


def _write_header(ws, headers, row=1):
    """写入表头行"""
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = HEADER_ALIGN
        c.border = THIN_BORDER


def _write_row(ws, row, values):
    """写入数据行"""
    for col, val in enumerate(values, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.font = CELL_FONT
        c.alignment = CELL_ALIGN
        c.border = THIN_BORDER


def export_collection_excel(data_dir, output_path, progress_callback=None):
    """导出收藏夹信息Excel（简化版，不含嵌入图片）"""
    info_dir = os.path.join(data_dir, '收藏夹信息')
    files = [f for f in os.listdir(info_dir) if f.endswith('.json')]
    wb = Workbook()
    # 删除默认sheet
    wb.remove(wb.active)

    headers = ['标题', 'UP主', '播放量', '收藏量', '弹幕', '时长', 'BV号', '上传时间', '收藏时间', '所属收藏夹']

    for idx, filename in enumerate(files, 1):
        folder_name = filename.replace('.json', '')
        if progress_callback:
            progress_callback(f'[{idx}/{len(files)}] {folder_name}')

        ws = wb.create_sheet(title=folder_name[:31])
        _write_header(ws, headers)

        with open(os.path.join(info_dir, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)

        for row_idx, v in enumerate(data.values(), 2):
            values = [
                v['视频信息']['标题'],
                v['up主']['昵称'],
                v['观众数据']['播放量'],
                v['观众数据']['收藏量'],
                v['观众数据']['弹幕数量'],
                v['视频信息']['时长'],
                v['BV'],
                v['三个时间']['上传时间'],
                v['三个时间']['收藏时间'],
                folder_name,
            ]
            _write_row(ws, row_idx, values)

        # 设置列宽
        widths = [50, 18, 12, 12, 10, 10, 16, 20, 20, 18]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w

    wb.save(output_path)
    if progress_callback:
        progress_callback(f'导出完成: {output_path}')
    return output_path


def export_study_excel(data_dir, output_path, progress_callback=None):
    """导出学习教程精选Excel"""
    from video_filter import filter_study_videos
    videos = filter_study_videos(data_dir)

    wb = Workbook()
    ws = wb.active
    ws.title = '学习教程精选'

    headers = ['排名', '标题', 'UP主', '收藏量', '播放量', '得分', '收藏夹', '链接']
    _write_header(ws, headers)

    for i, v in enumerate(videos, 1):
        url = f'https://bilibili.com/video/{v["BV"]}'
        values = [i, v['视频信息']['标题'], v['up主']['昵称'],
                  v['观众数据']['收藏量'], v['观众数据']['播放量'],
                  v['得分'], v['收藏夹'], url]
        _write_row(ws, i + 1, values)

    widths = [6, 55, 18, 12, 12, 10, 18, 45]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    wb.save(output_path)
    if progress_callback:
        progress_callback(f'导出完成: {output_path}')
    return output_path


def export_value_excel(data_dir, output_path, progress_callback=None):
    """导出有价值视频推荐Excel"""
    from video_filter import score_all_videos
    videos = score_all_videos(data_dir)

    wb = Workbook()
    ws = wb.active
    ws.title = '总榜 Top100'

    headers = ['排名', '标题', 'UP主', '收藏量', '播放量', '得分', '分类', '收藏夹']
    _write_header(ws, headers)

    for i, v in enumerate(videos[:100], 1):
        values = [i, v['视频信息']['标题'], v['up主']['昵称'],
                  v['观众数据']['收藏量'], v['观众数据']['播放量'],
                  v['得分'], v['分类'], v['收藏夹']]
        _write_row(ws, i + 1, values)

    widths = [6, 55, 18, 12, 12, 10, 15, 18]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    wb.save(output_path)
    if progress_callback:
        progress_callback(f'导出完成: {output_path}')
    return output_path
