"""配置管理模块 - 管理用户配置和爬取快照"""
import json
import os
import time

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
BASE_DIR = os.path.dirname(__file__)

DEFAULT_CONFIG = {
    'uid': '',
    'cookie': '',
    'active_session': '',  # 当前激活的快照ID
}


def load():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    return DEFAULT_CONFIG.copy()


def save(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def is_configured():
    cfg = load()
    return bool(cfg.get('uid')) and bool(cfg.get('cookie'))


# ========== 快照管理 ==========

def get_sessions_dir():
    """获取快照根目录"""
    d = os.path.join(BASE_DIR, 'sessions')
    os.makedirs(d, exist_ok=True)
    return d


def create_session():
    """创建新快照，返回快照ID和路径"""
    sid = time.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(get_sessions_dir(), sid)
    os.makedirs(path, exist_ok=True)
    for sub in ['收藏夹信息', '视频封面', 'up头像']:
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    # 写入元信息
    meta = {'id': sid, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'video_count': 0, 'folder_count': 0}
    with open(os.path.join(path, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    # 激活此快照
    cfg = load()
    cfg['active_session'] = sid
    save(cfg)
    return sid, path


def get_session_path(sid):
    """获取指定快照的路径"""
    return os.path.join(get_sessions_dir(), sid)


def get_active_session():
    """获取当前激活的快照ID"""
    cfg = load()
    sid = cfg.get('active_session', '')
    if sid and os.path.exists(get_session_path(sid)):
        return sid
    # 如果没有或已删除，取最新的
    sessions = list_sessions()
    if sessions:
        sid = sessions[0]['id']
        cfg['active_session'] = sid
        save(cfg)
        return sid
    return ''


def get_active_path(*args):
    """获取当前激活快照下的路径"""
    sid = get_active_session()
    if not sid:
        return os.path.join(BASE_DIR, 'data', *args)
    return os.path.join(get_session_path(sid), *args)


def list_sessions():
    """列出所有快照，按时间倒序"""
    sessions_dir = get_sessions_dir()
    result = []
    for sid in sorted(os.listdir(sessions_dir), reverse=True):
        meta_path = os.path.join(sessions_dir, sid, 'meta.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            result.append(meta)
    return result


def activate_session(sid):
    """切换激活的快照"""
    cfg = load()
    cfg['active_session'] = sid
    save(cfg)


def delete_session(sid):
    """删除快照"""
    import shutil
    path = get_session_path(sid)
    if os.path.exists(path):
        shutil.rmtree(path)
    # 如果删的是当前激活的，切换到最新的
    cfg = load()
    if cfg.get('active_session') == sid:
        sessions = list_sessions()
        cfg['active_session'] = sessions[0]['id'] if sessions else ''
        save(cfg)
