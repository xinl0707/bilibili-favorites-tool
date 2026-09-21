"""视频筛选模块 - 基于收藏夹分类 + AI辅助筛选"""
import json
import os


# 收藏夹分类映射（用户自己的分类体系）
FOLDER_CATEGORY = {
    'A学习': '学习',
    '学习': '学习',
    'aaa本周看': '学习',
    '语文': '学习',
    '知识区': '知识',
    '科技（包括科普）': '知识',
    '原神': '游戏',
    '崩坏_绝区零_星穹铁道': '游戏',
    'R6': '游戏',
    '端游': '游戏',
    '吃瓜烂游 幻塔_和平_明日_Q飞': '游戏',
    '音游': '游戏',
    '鬼畜 搞笑': '娱乐',
    '音乐': '娱乐',
    '生活区': '生活',
    '美食': '生活',
    '新闻': '资讯',
    'CV圈': '二次元',
    'ES': '二次元',
    '乙游_女性向': '二次元',
    'UP主收藏夹': '关注',
    '谷子': '二次元',
    '其他': '其他',
    'A学完': '学习',
    'h': '其他',
    '2.5次元': '二次元',
}

# 默认收藏夹的子分类（通过标题分析）
DEFAULT_FOLDER_KEYWORDS = {
    '编程/AI': ['python', 'java', 'c++', '编程', '代码', '开发', '程序员',
                'chatgpt', 'claude', 'cursor', 'ai', '大模型', 'mcp', 'agent',
                'github', 'git', 'linux', '前端', '后端', '算法', '数据结构'],
    '学习': ['教程', '入门', '进阶', '实战', '从零', '自学', '手把手',
             '考研', '考公', '四六级', '雅思', '托福', '论文', '科研',
             '数学', '物理', '化学', '生物', '英语', '日语', '韩语'],
    '设计/创作': ['剪辑', 'pr', 'ps', 'ae', '设计', 'procreate', 'figma',
                 'ppt', 'excel', 'word', '建模', '摄影', '调色'],
    '数码/硬件': ['笔记本', '电脑', '硬件', '数码', '手机', '耳机',
                 '智能家居', '自动化', '树莓派'],
    '工具/效率': ['软件', '工具', '插件', '神器', '开源', '部署', '效率',
                 '时间管理', '学习方法', '背单词'],
    '生活': ['面试', '求职', '就业', '理财', '投资', '心理', '哲学'],
    '娱乐': ['搞笑', '鬼畜', '整活', 'meme', '沙雕'],
    '游戏': ['原神', '崩坏', '星穹铁道', '绝区零', '游戏', 'steam'],
    '二次元': ['cosplay', '漫展', '同人', '偶像', 'es', '乙游'],
}


def _classify_default_folder(title, intro):
    """对默认收藏夹的视频进行子分类"""
    text = (title + ' ' + intro).lower()
    scores = {}
    for cat, keywords in DEFAULT_FOLDER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return '默认收藏夹/未分类'


def load_all_videos(data_dir):
    """加载所有视频数据"""
    info_dir = os.path.join(data_dir, '收藏夹信息')
    all_videos = []
    seen_bv = set()

    for filename in os.listdir(info_dir):
        if not filename.endswith('.json'):
            continue
        folder_name = filename.replace('.json', '')
        with open(os.path.join(info_dir, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
        for v in data.values():
            if v.get('是否失效'):
                continue
            bv = v.get('BV', '')
            if bv in seen_bv:
                continue
            seen_bv.add(bv)
            v['收藏夹'] = folder_name
            # 主分类：用收藏夹名字
            v['分类'] = FOLDER_CATEGORY.get(folder_name, folder_name)
            # 默认收藏夹的子分类
            if folder_name == '默认收藏夹':
                v['子分类'] = _classify_default_folder(
                    v['视频信息']['标题'], v['视频信息']['简介']
                )
            else:
                v['子分类'] = v['分类']
            all_videos.append(v)
    return all_videos


def filter_study_videos(data_dir):
    """筛选学习相关视频"""
    all_videos = load_all_videos(data_dir)
    # 只保留学习/知识/工具类，以及默认收藏夹中的学习子类
    study_folders = {'学习', '知识'}
    results = []
    for v in all_videos:
        cat = v['分类']
        sub = v.get('子分类', '')
        is_study_folder = cat in study_folders
        is_study_sub = sub in {'编程/AI', '学习', '设计/创作', '工具/效率', '数码/硬件'}
        is_default_study = cat == '默认收藏夹' and is_study_sub
        if is_study_folder or is_default_study:
            v['得分'] = v['观众数据']['收藏量'] * 2 + v['观众数据']['播放量'] * 0.01
            results.append(v)

    results.sort(key=lambda x: x['得分'], reverse=True)
    return results


def score_all_videos(data_dir):
    """给所有视频打分"""
    all_videos = load_all_videos(data_dir)
    for v in all_videos:
        v['得分'] = v['观众数据']['收藏量'] * 3 + v['观众数据']['播放量'] * 0.01
    all_videos.sort(key=lambda x: x['得分'], reverse=True)
    return all_videos


def get_categories(data_dir):
    """获取分类统计"""
    videos = filter_study_videos(data_dir)
    cats = {}
    for v in videos:
        # 用子分类作为最终分类
        cat = v.get('子分类', v['分类'])
        if cat not in cats:
            cats[cat] = 0
        cats[cat] += 1
    return dict(sorted(cats.items(), key=lambda x: -x[1]))
