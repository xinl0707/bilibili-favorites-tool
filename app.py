"""B站收藏夹工具 - Flask Web应用主程序"""
import json
import os
import re
import threading
import time as _time
from flask import Flask, render_template, request, jsonify, send_file
from urllib.parse import quote

import config
import crawler
import errors
import excel_export
import video_filter

app = Flask(__name__)

crawl_state = {
    'running': False,
    'progress': [],
    'done': False,
    'error': None,        # 原始错误消息（兼容旧版）
    'error_info': None,   # 结构化错误信息（新版）
    'session_id': '',
}

@app.route('/')
def index():
    cfg = config.load()
    configured = config.is_configured()
    sessions = config.list_sessions()
    active = config.get_active_session()
    stats = {}
    if active:
        info_dir = os.path.join(config.get_session_path(active), '收藏夹信息')
        if os.path.exists(info_dir):
            json_files = [f for f in os.listdir(info_dir) if f.endswith('.json')]
            total = 0
            for f in json_files:
                with open(os.path.join(info_dir, f), 'r', encoding='utf-8') as fp:
                    total += len(json.load(fp))
            stats = {'folders': len(json_files), 'videos': total}
    return render_template('index.html', configured=configured, stats=stats,
                           sessions=sessions, active_session=active)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        uid = request.form.get('uid', '').strip()
        cookie = request.form.get('cookie', '').strip()
        if not cookie:
            return jsonify({'ok': False, 'msg': 'Cookie不能为空'})
        if '---SPLIT---' in cookie:
            parts = cookie.split('---SPLIT---')
            if not uid:
                uid = parts[0].strip()
            cookie = parts[-1].strip()
        if not uid:
            m = re.search(r'DedeUserID=(\d+)', cookie)
            if m:
                uid = m.group(1)
        if uid and cookie:
            if 'SESSDATA=' not in cookie:
                return jsonify({'ok': False, 'msg': 'Cookie缺少SESSDATA，请从Network标签获取完整Cookie'})
            cfg = config.load()
            cfg['uid'] = uid
            cfg['cookie'] = cookie
            config.save(cfg)
            return jsonify({'ok': True, 'msg': '保存成功'})
        return jsonify({'ok': False, 'msg': '无法从Cookie中提取UID'})
    cfg = config.load()
    active = config.get_active_session()
    return render_template('settings.html', uid=cfg.get('uid', ''), cookie=cfg.get('cookie', ''), active_session=active)


@app.route('/crawl')
def crawl_page():
    sessions = config.list_sessions()
    active = config.get_active_session()
    return render_template('crawl.html', sessions=sessions, active_session=active)


@app.route('/browse')
def browse_page():
    active = config.get_active_session()
    return render_template('browse.html', active_session=active)


@app.route('/study')
def study_page():
    active = config.get_active_session()
    return render_template('study.html', active_session=active)


# ========== 爬取API ==========

@app.route('/api/crawl/start', methods=['POST'])
def start_crawl():
    if crawl_state['running']:
        return jsonify({'ok': False, 'msg': '正在爬取中'})
    if not config.is_configured():
        return jsonify({'ok': False, 'msg': '请先配置Cookie'})

    # 创建新快照
    sid, session_path = config.create_session()
    crawl_state['running'] = True
    crawl_state['done'] = False
    crawl_state['error'] = None
    crawl_state['error_info'] = None
    crawl_state['progress'] = []
    crawl_state['session_id'] = sid

    def run():
        try:
            cfg = config.load()
            def cb(msg):
                crawl_state['progress'].append(msg)

            crawler.crawl_all(cfg['uid'], cfg['cookie'], session_path, cb)
            crawler.download_covers(session_path, cb)
            crawler.download_avatars(session_path, cb)

            # 更新元信息
            info_dir = os.path.join(session_path, '收藏夹信息')
            json_files = [f for f in os.listdir(info_dir) if f.endswith('.json')]
            total = 0
            for f in json_files:
                with open(os.path.join(info_dir, f), 'r', encoding='utf-8') as fp:
                    total += len(json.load(fp))
            meta_path = os.path.join(session_path, 'meta.json')
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            meta['video_count'] = total
            meta['folder_count'] = len(json_files)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            crawl_state['done'] = True
        except Exception as e:
            raw_msg = str(e)
            crawl_state['error'] = raw_msg
            # 结构化错误分类
            classified = errors.classify_error(raw_msg)
            if classified:
                crawl_state['error_info'] = {
                    'code': classified.code,
                    'title': classified.title,
                    'message': classified.message,
                    'category': classified.category,
                    'severity': classified.severity.value,
                    'cause': classified.cause,
                    'solution': classified.solution,
                    'suggestion': classified.suggestion or '',
                }
            else:
                crawl_state['error_info'] = {
                    'code': 'SYS-001',
                    'title': '未知系统错误',
                    'message': raw_msg[:300],
                    'category': '系统错误',
                    'severity': 'fatal',
                    'cause': '发生了未被分类的异常。',
                    'solution': ['1. 查看完整错误信息', '2. 尝试重新运行', '3. 如持续出现，请反馈此问题'],
                    'suggestion': '',
                }
        finally:
            crawl_state['running'] = False

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return jsonify({'ok': True, 'msg': '爬取已启动', 'session': sid})


@app.route('/api/crawl/status')
def crawl_status():
    return jsonify({
        'running': crawl_state['running'],
        'done': crawl_state['done'],
        'error': crawl_state['error'],
        'error_info': crawl_state['error_info'],
        'progress': crawl_state['progress'][-30:],
        'session': crawl_state['session_id'],
    })


@app.route('/api/crawl/errors')
def api_crawl_errors():
    """获取所有可能的错误类型（用于前端展示和模拟）"""
    all_errors = errors.get_all_errors()
    result = []
    for e in all_errors:
        result.append({
            'code': e.code,
            'title': e.title,
            'message': e.message,
            'category': e.category,
            'severity': e.severity.value,
            'cause': e.cause,
            'solution': e.solution,
            'suggestion': e.suggestion or '',
        })
    return jsonify(result)


@app.route('/api/crawl/simulate/<error_code>')
def api_simulate_error(error_code):
    """模拟特定错误（用于演示错误提示效果）"""
    err = errors.get_error_by_code(error_code.upper())
    if not err:
        return jsonify({'ok': False, 'msg': f'未知错误码: {error_code}'})
    # 将模拟错误写入crawl_state
    crawl_state['error'] = f'[模拟] {err.message}'
    crawl_state['error_info'] = {
        'code': err.code,
        'title': err.title,
        'message': err.message,
        'category': err.category,
        'severity': err.severity.value,
        'cause': err.cause,
        'solution': err.solution,
        'suggestion': err.suggestion or '',
        'simulated': True,
    }
    crawl_state['done'] = True
    crawl_state['running'] = False
    return jsonify({'ok': True, 'msg': f'已模拟错误: {err.title}'})


# ========== 快照管理API ==========

@app.route('/api/sessions')
def api_sessions():
    return jsonify(config.list_sessions())


@app.route('/api/sessions/activate', methods=['POST'])
def api_activate_session():
    data = request.json or {}
    sid = data.get('id', '')
    sessions = config.list_sessions()
    ids = [s['id'] for s in sessions]
    if sid not in ids:
        return jsonify({'ok': False, 'msg': '快照不存在'})
    config.activate_session(sid)
    return jsonify({'ok': True})


@app.route('/api/sessions/delete', methods=['POST'])
def api_delete_session():
    data = request.json or {}
    sid = data.get('id', '')
    if not sid:
        return jsonify({'ok': False, 'msg': '缺少id'})
    config.delete_session(sid)
    return jsonify({'ok': True})


# ========== 数据API ==========

def _get_data_dir():
    sid = config.get_active_session()
    if not sid:
        return None
    return config.get_session_path(sid)


@app.route('/api/videos')
def api_videos():
    data_dir = _get_data_dir()
    if not data_dir or not os.path.exists(os.path.join(data_dir, '收藏夹信息')):
        return jsonify([])
    all_videos = video_filter.load_all_videos(data_dir)
    all_videos.sort(key=lambda x: x['观众数据']['收藏量'], reverse=True)
    result = []
    for v in all_videos:
        result.append({
            'BV': v['BV'], '标题': v['视频信息']['标题'],
            '简介': v['视频信息'].get('简介', ''),
            'UP': v['up主']['昵称'], 'UP_ID': v['up主']['ID'],
            '封面': f'/images/covers/{quote(v["收藏夹"])}/{v["BV"]}.jpg',
            '头像': f'/images/avatars/{v["up主"]["ID"]}.jpg',
            '播放': v['观众数据']['播放量'], '收藏': v['观众数据']['收藏量'],
            '弹幕': v['观众数据']['弹幕数量'], '时长': v['视频信息']['时长'],
            '上传时间': v['三个时间']['上传时间'],
            '发布时间': v['三个时间']['发布时间'],
            '收藏时间': v['三个时间']['收藏时间'],
            '收藏夹': v['收藏夹'], '分类': v['分类'],
            '链接': f'https://bilibili.com/video/{v["BV"]}',
        })
    return jsonify(result)


@app.route('/api/folders')
def api_folders():
    data_dir = _get_data_dir()
    if not data_dir or not os.path.exists(os.path.join(data_dir, '收藏夹信息')):
        return jsonify([])
    info_dir = os.path.join(data_dir, '收藏夹信息')
    return jsonify(sorted([f.replace('.json', '') for f in os.listdir(info_dir) if f.endswith('.json')]))


@app.route('/api/study')
def api_study():
    data_dir = _get_data_dir()
    if not data_dir or not os.path.exists(os.path.join(data_dir, '收藏夹信息')):
        return jsonify([])
    videos = video_filter.filter_study_videos(data_dir)
    result = []
    for v in videos:
        result.append({
            'BV': v['BV'], '标题': v['视频信息']['标题'],
            '简介': v['视频信息'].get('简介', ''),
            'UP': v['up主']['昵称'], 'UP_ID': v['up主']['ID'],
            '封面': f'/images/covers/{quote(v["收藏夹"])}/{v["BV"]}.jpg',
            '头像': f'/images/avatars/{v["up主"]["ID"]}.jpg',
            '播放': v['观众数据']['播放量'], '收藏': v['观众数据']['收藏量'],
            '弹幕': v['观众数据']['弹幕数量'], '时长': v['视频信息']['时长'],
            '上传时间': v['三个时间']['上传时间'],
            '发布时间': v['三个时间']['发布时间'],
            '收藏时间': v['三个时间']['收藏时间'],
            '得分': v['得分'], '分类': v['分类'],
            '收藏夹': v['收藏夹'],
            '链接': f'https://bilibili.com/video/{v["BV"]}',
        })
    return jsonify(result)


@app.route('/api/categories')
def api_categories():
    data_dir = _get_data_dir()
    if not data_dir:
        return jsonify({})
    return jsonify(video_filter.get_categories(data_dir))


# ========== 导出 ==========

@app.route('/export/<export_type>')
def export_excel(export_type):
    data_dir = _get_data_dir()
    if not data_dir:
        return jsonify({'ok': False, 'msg': '没有可导出的数据'})
    sid = config.get_active_session()
    output_dir = os.path.join(data_dir, '导出')
    os.makedirs(output_dir, exist_ok=True)
    timestamp = _time.strftime('%Y%m%d_%H%M%S')
    type_names = {'collection': '收藏夹信息', 'study': '学习教程精选', 'value': '有价值视频推荐'}
    type_name = type_names.get(export_type, export_type)
    filename = f'{type_name}_{timestamp}.xlsx'
    path = os.path.join(output_dir, filename)
    if export_type == 'collection':
        excel_export.export_collection_excel(data_dir, path)
    elif export_type == 'study':
        excel_export.export_study_excel(data_dir, path)
    elif export_type == 'value':
        excel_export.export_value_excel(data_dir, path)
    else:
        return jsonify({'ok': False, 'msg': '未知类型'})
    return send_file(path, as_attachment=True, download_name=filename)


@app.route('/export/download/<filename>')
def download_export(filename):
    if '..' in filename or '/' in filename:
        return 'Invalid', 400
    data_dir = _get_data_dir()
    if not data_dir:
        return 'No session', 404
    path = os.path.join(data_dir, '导出', filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=filename)
    return 'Not found', 404


@app.route('/api/exports')
def list_exports():
    data_dir = _get_data_dir()
    if not data_dir:
        return jsonify([])
    export_dir = os.path.join(data_dir, '导出')
    if not os.path.exists(export_dir):
        return jsonify([])
    files = []
    for f in os.listdir(export_dir):
        if f.endswith('.xlsx'):
            p = os.path.join(export_dir, f)
            st = os.stat(p)
            files.append({
                'name': f, 'size': st.st_size,
                'time': _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(st.st_mtime)),
            })
    files.sort(key=lambda x: x['time'], reverse=True)
    return jsonify(files)


@app.route('/api/exports/delete', methods=['POST'])
def delete_export():
    data = request.json or {}
    filename = data.get('filename', '')
    if not filename or '..' in filename:
        return jsonify({'ok': False, 'msg': '无效'})
    data_dir = _get_data_dir()
    if not data_dir:
        return jsonify({'ok': False, 'msg': '无快照'})
    path = os.path.join(data_dir, '导出', filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': '不存在'})


# ========== 图片代理 ==========

@app.route('/images/covers/<path:folder>/<filename>')
def serve_cover(folder, filename):
    data_dir = _get_data_dir()
    if not data_dir:
        return '', 404
    path = os.path.join(data_dir, '视频封面', folder, filename)
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return '', 404


@app.route('/images/avatars/<filename>')
def serve_avatar(filename):
    data_dir = _get_data_dir()
    if not data_dir:
        return '', 404
    path = os.path.join(data_dir, 'up头像', filename)
    if os.path.exists(path):
        return send_file(path, mimetype='image/jpeg')
    return '', 404


if __name__ == '__main__':
    import threading
    import webbrowser
    # 服务器启动后自动打开浏览器
    threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(host='0.0.0.0', port=5000, debug=False)
