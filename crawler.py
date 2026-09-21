"""B站收藏夹爬虫模块 - 从B站API爬取收藏夹数据"""
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
}


def _get_headers(cookie):
    """构建带Cookie的请求头"""
    h = HEADERS.copy()
    h['cookie'] = cookie
    return h


def _safe_request(url, params, headers, timeout=15, retries=3):
    """带重试的安全请求"""
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url=url, params=params, headers=headers, timeout=timeout)
            # 检查HTTP状态码
            if resp.status_code == 412:
                raise ValueError(f"B站返回412状态码：触发反爬虫限流，请等待10-30分钟后重试。")
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 0:
                code = data.get('code')
                msg = data.get('message', '未知错误')
                if code == -101:
                    raise ValueError(f"API错误(code={code}): {msg} — Cookie可能已过期，请重新获取Cookie")
                elif code == -509:
                    raise ValueError(f"API错误(code={code}): {msg} — 请求过于频繁，触发风控，请等待10-30分钟")
                elif code == -403:
                    raise ValueError(f"API错误(code={code}): {msg} — 权限不足，请检查收藏夹是否已公开")
                else:
                    raise ValueError(f"API错误(code={code}): {msg}")
            return data
        except ValueError:
            raise
        except requests.exceptions.Timeout as e:
            last_error = ValueError(f"网络请求超时: 连接 api.bilibili.com 超时(>{timeout}s)，请检查网络连接")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.ConnectionError as e:
            err_str = str(e).lower()
            if 'dns' in err_str or 'getaddrinfo' in err_str or 'name or service not known' in err_str:
                last_error = ValueError(f"DNS解析失败: 无法解析 api.bilibili.com 域名，请检查DNS设置")
            elif 'refused' in err_str:
                last_error = ValueError(f"连接被拒绝: B站服务器拒绝了连接请求，请等待几分钟后重试")
            elif 'ssl' in err_str or 'certificate' in err_str:
                last_error = ValueError(f"SSL证书错误: 请检查系统时间是否正确，关闭抓包工具后重试")
            else:
                last_error = ValueError(f"网络连接错误: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
        except requests.exceptions.RequestException as e:
            last_error = ValueError(f"网络请求异常: {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
        except json.JSONDecodeError as e:
            last_error = ValueError(f"JSON解析失败: API返回的数据格式异常，B站可能返回了错误页面")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last_error


def _sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def get_favorite_id(uid, cookie, data_dir):
    """获取所有收藏夹的ID列表"""
    url = 'https://api.bilibili.com/x/v3/fav/folder/created/list-all'
    params = {'up_mid': uid, 'jsonp': 'jsonp'}
    headers = _get_headers(cookie)

    data = _safe_request(url, params, headers)
    id_file = os.path.join(data_dir, '收藏夹信息', '收藏夹id.json')
    with open(id_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def get_one_favorite(media_id, max_page, cookie, progress_callback=None):
    """爬取一个收藏夹的所有页"""
    url = 'https://api.bilibili.com/x/v3/fav/resource/list'
    params = {
        'ps': 20, 'keyword': '', 'order': 'mtime', 'type': 0,
        'tid': 0, 'platform': 'web', 'jsonp': 'jsonp',
        'pn': 1, 'media_id': media_id
    }
    headers = _get_headers(cookie)

    all_data = {}
    for page in range(1, max_page + 1):
        params['pn'] = page
        if progress_callback:
            progress_callback(f'第{page}/{max_page}页')
        try:
            resp = _safe_request(url, params, headers)
            resp_data = resp.get('data') or {}
            medias = resp_data.get('medias')
            if not medias:
                break
            for item in medias:
                all_data[item['id']] = item
        except Exception as e:
            if progress_callback:
                progress_callback(f'第{page}页失败: {e}')
        time.sleep(0.5)
    return all_data


def process_raw_data(raw_data):
    """处理原始API数据，提取关键信息"""
    result = {}
    for item in raw_data.values():
        try:
            media = {
                'id': item['id'],
                'BV': item['bv_id'],
                '是否失效': False,
                'up主': {
                    'ID': item['upper']['mid'],
                    '昵称': item['upper']['name'],
                    '头像': item['upper']['face']
                },
                '视频信息': {
                    '标题': item['title'],
                    '封面': item['cover'],
                    '简介': item.get('intro', ''),
                    '时长': time.strftime("%H:%M:%S", time.gmtime(item['duration']))
                },
                '观众数据': {
                    '播放量': item['cnt_info']['play'],
                    '收藏量': item['cnt_info']['collect'],
                    '弹幕数量': item['cnt_info']['danmaku']
                },
                '三个时间': {
                    '上传时间': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['ctime'])),
                    '发布时间': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['pubtime'])),
                    '收藏时间': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['fav_time']))
                }
            }
            result[media['id']] = media
        except (KeyError, TypeError):
            continue
    return result


def compare_last_time(file_path, new_data):
    """对比上次爬取数据，标记失效和取消收藏"""
    if not os.path.exists(file_path):
        return new_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return new_data

    # 视频被删除，保留旧数据并标记
    for video in list(new_data.values()):
        if video['视频信息']['标题'] == '已失效视频' and str(video['id']) in old_data:
            old_entry = old_data[str(video['id'])]
            old_entry['是否失效'] = True
            new_data[video['id']] = old_entry

    # 用户取消收藏，标记
    for old_id, old_video in old_data.items():
        if old_video.get('id') not in new_data:
            old_video['是否取消了收藏'] = True
            new_data[old_video['id']] = old_video

    return new_data


def crawl_all(uid, cookie, data_dir, progress_callback=None):
    """爬取全部收藏夹"""
    info_dir = os.path.join(data_dir, '收藏夹信息')
    os.makedirs(info_dir, exist_ok=True)

    if progress_callback:
        progress_callback('正在获取收藏夹列表...')

    # 获取收藏夹ID
    id_data = get_favorite_id(uid, cookie, data_dir)
    data = id_data.get('data') or {}
    folder_list = data.get('list', [])
    if not folder_list:
        if progress_callback:
            progress_callback('未找到收藏夹，请确认收藏夹已公开')
        return

    total_folders = len(folder_list)
    for idx, folder in enumerate(folder_list, 1):
        folder_name = _sanitize_filename(folder['title'])
        safe_name = folder_name
        file_path = os.path.join(info_dir, f'{safe_name}.json')

        if progress_callback:
            progress_callback(f'[{idx}/{total_folders}] 爬取: {folder["title"]}')

        # 计算页数
        max_page = math.ceil(folder['media_count'] / 20) + 1
        raw = get_one_favorite(
            folder['id'], max_page, cookie,
            progress_callback=lambda msg: progress_callback(f'[{idx}/{total_folders}] {folder["title"]}: {msg}') if progress_callback else None
        )

        processed = process_raw_data(raw)
        final = compare_last_time(file_path, processed)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(final, f, ensure_ascii=False)

        time.sleep(1)

    # 删除临时文件
    temp_id_file = os.path.join(info_dir, '收藏夹id.json')
    if os.path.exists(temp_id_file):
        os.remove(temp_id_file)

    if progress_callback:
        progress_callback(f'爬取完成！共 {total_folders} 个收藏夹')


def collect_photo_urls(data_dir):
    """从JSON文件中提取封面和头像URL"""
    info_dir = os.path.join(data_dir, '收藏夹信息')
    cover_urls = {}
    avatar_urls = {}

    for filename in os.listdir(info_dir):
        if not filename.endswith('.json'):
            continue
        file_path = os.path.join(info_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        folder_name = filename.replace('.json', '')
        covers = {}
        for v in data.values():
            bv = v.get('BV', '')
            cover = v.get('视频信息', {}).get('封面', '')
            if cover and cover.startswith('http'):
                covers[bv] = cover
            # 头像
            up_id = v.get('up主', {}).get('ID', '')
            face = v.get('up主', {}).get('头像', '')
            if up_id and face and face.startswith('http'):
                avatar_urls[str(up_id)] = face

        cover_urls[folder_name] = covers
    return cover_urls, avatar_urls


def download_covers(data_dir, progress_callback=None):
    """多线程下载视频封面"""
    cover_urls, _ = collect_photo_urls(data_dir)
    cover_dir = os.path.join(data_dir, '视频封面')
    os.makedirs(cover_dir, exist_ok=True)

    total = sum(len(v) for v in cover_urls.values())
    count = 0

    for folder_name, covers in cover_urls.items():
        folder_path = os.path.join(cover_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        urls = list(covers.items())
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for bv, url in urls:
                future = executor.submit(requests.get, url, timeout=15)
                futures[future] = bv

            for future in as_completed(futures):
                bv = futures[future]
                count += 1
                try:
                    resp = future.result()
                    img_path = os.path.join(folder_path, f'{bv}.jpg')
                    with open(img_path, 'wb') as f:
                        f.write(resp.content)
                except Exception:
                    pass
                if progress_callback and count % 10 == 0:
                    progress_callback(f'封面: {count}/{total}')

    if progress_callback:
        progress_callback(f'封面下载完成: {total}张')


def download_avatars(data_dir, progress_callback=None):
    """多线程下载UP主头像"""
    _, avatar_urls = collect_photo_urls(data_dir)
    avatar_dir = os.path.join(data_dir, 'up头像')
    os.makedirs(avatar_dir, exist_ok=True)

    total = len(avatar_urls)
    count = 0

    urls = list(avatar_urls.items())
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for up_id, url in urls:
            future = executor.submit(requests.get, url, timeout=15)
            futures[future] = up_id

        for future in as_completed(futures):
            up_id = futures[future]
            count += 1
            try:
                resp = future.result()
                img_path = os.path.join(avatar_dir, f'{up_id}.jpg')
                with open(img_path, 'wb') as f:
                    f.write(resp.content)
            except Exception:
                pass
            if progress_callback and count % 10 == 0:
                progress_callback(f'头像: {count}/{total}')

    if progress_callback:
        progress_callback(f'头像下载完成: {total}张')
