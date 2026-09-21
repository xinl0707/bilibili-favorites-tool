"""爬取错误分类与知识库 — 结构化错误诊断 + 解决方案"""
import re
from enum import Enum


class Severity(Enum):
    FATAL = 'fatal'        # 无法继续，必须修复
    PARTIAL = 'partial'    # 部分失败，可跳过继续
    WARNING = 'warning'    # 不影响结果，仅提醒


class CrawlError:
    """结构化爬取错误"""
    def __init__(self, code, title, message, category, severity, cause, solution, suggestion=''):
        self.code = code
        self.title = title
        self.message = message
        self.category = category
        self.severity = severity
        self.cause = cause          # 原因分析
        self.solution = solution    # 解决步骤（列表）
        self.suggestion = suggestion  # 额外建议


# ============================================================
# 错误知识库 — 所有已知爬取错误
# ============================================================
ERROR_KB = [
    CrawlError(
        code='COOKIE-001',
        title='Cookie 已过期',
        message='SESSDATA 已过期，B站API返回未登录状态',
        category='Cookie 问题',
        severity=Severity.FATAL,
        cause='B站 Cookie 中的 SESSDATA 字段有效期通常为 1-3 个月。过期后服务器无法识别你的登录身份，所有API请求都会返回 -101（账号未登录）。',
        solution=[
            '1. 打开 <a href="https://www.bilibili.com" target="_blank">bilibili.com</a> 并重新登录',
            '2. 按 F12 → Network（网络）标签 → 刷新页面',
            '3. 点击任意请求 → Request Headers → 复制完整 Cookie 值',
            '4. 回到本工具 <a href="/settings">设置页面</a>，粘贴新 Cookie',
            '5. 点击"保存配置"后重新爬取',
        ],
        suggestion='💡 建议使用无痕窗口登录B站后获取Cookie，可避免旧Cookie残留干扰。'
    ),
    CrawlError(
        code='COOKIE-002',
        title='Cookie 缺少 SESSDATA',
        message='Cookie 中未找到 SESSDATA 字段',
        category='Cookie 问题',
        severity=Severity.FATAL,
        cause='从浏览器控制台（Console）使用 document.cookie 获取的 Cookie 不包含 HttpOnly 字段（如 SESSDATA）。必须从 Network 标签的请求头中获取。',
        solution=[
            '1. 不要从 Console 执行 document.cookie 获取！',
            '2. 正确方法：F12 → Network → 刷新页面 → 点击任一 XHR 请求',
            '3. 在 Request Headers 中找到 Cookie 整行，复制全部内容',
            '4. 确保值中包含 <code>SESSDATA=xxx...</code>',
            '5. 粘贴到设置页保存',
        ],
        suggestion='💡 SESSDATA 是 HttpOnly Cookie，JS 无法读取，必须从网络请求头获取。'
    ),
    CrawlError(
        code='COOKIE-003',
        title='Cookie 格式异常',
        message='Cookie 格式无法解析，可能复制不完整',
        category='Cookie 问题',
        severity=Severity.FATAL,
        cause='Cookie 字符串包含了换行符、引号、或复制时遗漏了部分字段。有效的Cookie应该是单行、以分号分隔的键值对字符串。',
        solution=[
            '1. 确认复制的是完整的一行 Cookie 字符串',
            '2. 检查是否包含多余的空格或换行',
            '3. 至少需要包含: buvid3, b_nut, DedeUserID, SESSDATA, bili_jct',
            '4. 重新从 Network 标签完整复制',
        ],
        suggestion='💡 如果使用多行粘贴，工具会自动处理换行分割。'
    ),
    CrawlError(
        code='AUTH-001',
        title='账号未登录（-101）',
        message='B站API返回 -101：账号未登录',
        category='认证问题',
        severity=Severity.FATAL,
        cause='服务器认为当前请求未携带有效的登录凭证。可能是 Cookie 已过期、被篡改、或B站服务器强制下线了该会话。',
        solution=[
            '1. 重新登录 bilibili.com',
            '2. 按照设置页的指引获取全新 Cookie',
            '3. 在设置页保存后重试',
        ],
        suggestion='💡 如果在多设备同时登录，B站可能会踢掉旧会话，需要重新获取Cookie。'
    ),
    CrawlError(
        code='AUTH-002',
        title='账号被风控（-509）',
        message='B站API返回 -509：请求过于频繁，触发风控',
        category='认证问题',
        severity=Severity.FATAL,
        cause='短时间内发起了过多API请求，触发了B站的反爬虫风控机制。常见于短时间内重复爬取、或网络环境异常。',
        solution=[
            '1. 停止所有爬取操作',
            '2. 等待 10-30 分钟后再重试',
            '3. 如果持续被风控，建议更换IP或等待数小时',
            '4. 可尝试在浏览器中手动访问B站，完成人机验证',
        ],
        suggestion='💡 工具已内置请求间隔（每页0.5s），正常使用不易触发风控。如频繁出现，请检查是否同时运行了多个爬取任务。'
    ),
    CrawlError(
        code='AUTH-003',
        title='UID 与 Cookie 不匹配',
        message='Cookie 中的 UID 与配置的 UID 不一致',
        category='认证问题',
        severity=Severity.FATAL,
        cause='设置页面保存的UID与Cookie中的DedeUserID不一致。Cookie来自一个账号，UID却是另一个账号的。',
        solution=[
            '1. 去设置页面清空 UID 字段',
            '2. 重新粘贴完整的 Cookie',
            '3. 工具会自动从 Cookie 中提取正确的 UID',
            '4. 保存后重试',
        ],
        suggestion='💡 建议不要手动填写UID，让工具自动从Cookie中提取。'
    ),
    CrawlError(
        code='NET-001',
        title='网络连接超时',
        message='请求B站API超时，无法建立连接',
        category='网络问题',
        severity=Severity.PARTIAL,
        cause='客户端在规定时间内未能与B站服务器建立TCP连接或收到响应。可能原因：网络不稳定、DNS解析慢、代理/VPN干扰、防火墙阻断。',
        solution=[
            '1. 检查网络连接是否正常：打开 bilibili.com 确认可以访问',
            '2. 如果使用代理/VPN，尝试关闭后重试',
            '3. 检查防火墙是否阻止了Python的网络访问',
            '4. 尝试 ping api.bilibili.com 测试连通性',
            '5. 等待几分钟后重试（可能是B站服务器临时波动）',
        ],
        suggestion='💡 工具会自动重试3次，每次间隔递增。超时阈值15秒。'
    ),
    CrawlError(
        code='NET-002',
        title='DNS 解析失败',
        message='无法解析 api.bilibili.com 域名',
        category='网络问题',
        severity=Severity.FATAL,
        cause='DNS服务器无法将 api.bilibili.com 解析为IP地址。可能是本地DNS配置问题、DNS服务器故障、或网络环境限制。',
        solution=[
            '1. 检查DNS设置：尝试将DNS改为 114.114.114.114 或 8.8.8.8',
            '2. 在cmd中执行 <code>nslookup api.bilibili.com</code> 测试',
            '3. 检查hosts文件是否被修改',
            '4. 重启路由器或切换网络环境',
        ],
    ),
    CrawlError(
        code='NET-003',
        title='SSL 证书错误',
        message='B站API的SSL证书验证失败',
        category='网络问题',
        severity=Severity.FATAL,
        cause='系统时间不正确、根证书过期、或中间人代理（如Fiddler/Charles）干扰了HTTPS连接。',
        solution=[
            '1. 检查系统时间是否正确（年份/日期）',
            '2. 关闭抓包工具（Fiddler、Charles、mitmproxy等）',
            '3. 如果公司网络有SSL审查，尝试使用手机热点',
            '4. 更新操作系统的根证书',
        ],
    ),
    CrawlError(
        code='NET-004',
        title='连接被拒绝',
        message='B站服务器拒绝连接（Connection Refused）',
        category='网络问题',
        severity=Severity.PARTIAL,
        cause='B站服务器主动拒绝了连接请求。通常是服务端临时过载、IP被暂时封禁、或请求频率过高。',
        solution=[
            '1. 等待 5-15 分钟后重试',
            '2. 检查B站是否在维护中',
            '3. 降低爬取速度（工具已默认间隔0.5s/页）',
            '4. 尝试切换网络（如从WiFi切换到移动热点）',
        ],
        suggestion='💡 如频繁出现，可在爬取间隔中增加等待时间。'
    ),
    CrawlError(
        code='API-001',
        title='收藏夹列表为空',
        message='未找到任何收藏夹，可能收藏夹未公开',
        category='API 响应异常',
        severity=Severity.FATAL,
        cause='B站API返回了空的收藏夹列表。最常见的原因是：你的收藏夹隐私设置为"仅自己可见"，导致API无法读取。B站默认收藏夹是公开的，但用户可以手动改为私密。',
        solution=[
            '1. 打开 <a href="https://space.bilibili.com/" target="_blank">B站个人空间</a>',
            '2. 进入"收藏"页面 → 检查收藏夹是否可见',
            '3. 点击收藏夹旁的"编辑" → 将隐私设置为"公开"',
            '4. 确认修改后回到本工具重新爬取',
        ],
        suggestion='💡 只需将想爬取的收藏夹设为公开即可，不必全部公开。爬取完成后可改回私密。'
    ),
    CrawlError(
        code='API-002',
        title='单个收藏夹爬取失败',
        message='某个收藏夹的数据获取失败',
        category='API 响应异常',
        severity=Severity.PARTIAL,
        cause='某个特定收藏夹的API请求返回了异常数据。可能是该收藏夹包含被删除的视频、收藏夹ID异常、或临时网络波动。',
        solution=[
            '1. 重试通常可以解决（临时网络问题）',
            '2. 检查B站该收藏夹是否正常显示',
            '3. 如果持续出现，尝试在B站上打开该收藏夹确认状态',
        ],
        suggestion='💡 单个收藏夹失败不影响其他收藏夹的爬取，工具会继续处理下一个。'
    ),
    CrawlError(
        code='API-003',
        title='API 返回未知错误',
        message='B站API返回了未预期的错误码',
        category='API 响应异常',
        severity=Severity.PARTIAL,
        cause='B站API返回了非0的code值，但不在已知错误码范围内。可能是B站API接口变动、新增错误码、或请求参数异常。',
        solution=[
            '1. 记录错误详情（错误码+错误信息）',
            '2. 等待几分钟后重试',
            '3. 如果持续出现，可能是B站API变动，需要更新工具',
        ],
    ),
    CrawlError(
        code='API-004',
        title='请求过于频繁（412）',
        message='B站返回412状态码：触发反爬虫限流',
        category='API 响应异常',
        severity=Severity.FATAL,
        cause='HTTP 412状态码通常表示请求被B站的前端反爬系统拦截。可能原因：User-Agent异常、缺少必要的请求头、或访问频率超过了阈值。',
        solution=[
            '1. 等待 10-30 分钟',
            '2. 检查是否同时运行了多个爬取实例',
            '3. 尝试更换User-Agent（工具内置了Chrome UA）',
            '4. 如持续出现，建议第二天再试',
        ],
    ),
    CrawlError(
        code='DATA-001',
        title='JSON 数据解析失败',
        message='API返回的数据无法解析为JSON',
        category='数据解析问题',
        severity=Severity.PARTIAL,
        cause='服务器返回的不是有效的JSON格式。可能是B站返回了HTML错误页面（如502/503）、或被中间代理注入/篡改了响应内容。',
        solution=[
            '1. 检查B站是否正常运行（访问 bilibili.com 确认）',
            '2. 关闭可能篡改HTTP响应的代理/插件',
            '3. 等待几分钟后重试',
        ],
    ),
    CrawlError(
        code='DATA-002',
        title='视频数据字段缺失',
        message='API返回的视频数据缺少必要字段（标题/封面等）',
        category='数据解析问题',
        severity=Severity.WARNING,
        cause='部分视频的API数据中缺少某些字段。通常是该视频已被删除、下架、或转为私有，导致B站API返回了不完整的数据。',
        solution=[
            '1. 这是正常现象（B站上已失效的视频）',
            '2. 工具会自动跳过这些视频，不影响整体爬取',
            '3. 如果大量视频出现此问题，检查是否是B站API变动',
        ],
        suggestion='💡 这些视频在B站上可能显示为"视频已失效"或"啊叻？视频不见了？"。'
    ),
    CrawlError(
        code='STORE-001',
        title='磁盘空间不足',
        message='写入文件失败：磁盘空间不足',
        category='存储问题',
        severity=Severity.FATAL,
        cause='本地磁盘剩余空间不足以保存爬取的数据和图片。收藏夹数据量较大时（数千视频+封面），可能需要数百MB空间。',
        solution=[
            '1. 检查磁盘剩余空间',
            '2. 清理不需要的旧快照（在导航栏删除）',
            '3. 清理系统临时文件',
            '4. 如果空间充足但持续报错，检查目录写入权限',
        ],
    ),
    CrawlError(
        code='STORE-002',
        title='文件写入权限不足',
        message='无法写入文件：权限被拒绝（Permission Denied）',
        category='存储问题',
        severity=Severity.FATAL,
        cause='操作系统拒绝了Python进程的文件写入操作。可能原因：目录被设为只读、杀毒软件拦截、文件被其他程序占用。',
        solution=[
            '1. 右键工具目录 → 属性 → 取消"只读"',
            '2. 检查杀毒软件是否拦截了Python的文件操作',
            '3. 尝试以管理员身份运行',
            '4. 确认文件未被其他程序（如Excel）打开占用',
        ],
    ),
    CrawlError(
        code='DOWN-001',
        title='封面图片下载失败',
        message='部分视频封面图片下载超时或失败',
        category='下载问题',
        severity=Severity.WARNING,
        cause='B站图片CDN对频繁请求有一定限流，部分封面可能下载超时。或者是旧视频的封面链接已失效。',
        solution=[
            '1. 不影响核心数据（视频信息已完整保存）',
            '2. 工具已自动跳过失败的图片',
            '3. 可稍后重新爬取来补充缺失的封面',
        ],
        suggestion='💡 封面下载使用5线程并发，失败自动跳过，不影响视频数据。'
    ),
    CrawlError(
        code='DOWN-002',
        title='头像图片下载失败',
        message='部分UP主头像下载失败',
        category='下载问题',
        severity=Severity.WARNING,
        cause='同封面下载，CDN限流或旧头像链接失效导致。',
        solution=[
            '1. 不影响核心数据',
            '2. 工具已自动跳过',
            '3. 头像仅用于浏览页面的UP主标识，缺失时会显示默认图标',
        ],
    ),
    CrawlError(
        code='SYS-001',
        title='未知系统错误',
        message='爬取过程中发生了未预期的异常',
        category='系统错误',
        severity=Severity.FATAL,
        cause='发生了未被分类的异常。可能是Python环境问题、依赖库版本不兼容、或极少见的边界情况。',
        solution=[
            '1. 查看完整的错误堆栈信息',
            '2. 检查Python版本（建议3.8+）',
            '3. 尝试重新安装依赖：pip install -r requirements.txt',
            '4. 重启工具后重试',
        ],
    ),
]


# ============================================================
# 错误匹配逻辑
# ============================================================

def classify_error(error_message: str, context: dict = None) -> CrawlError:
    """根据错误信息匹配对应的结构化错误"""
    if not error_message:
        return None

    msg_lower = error_message.lower()
    context = context or {}

    # 按优先级匹配（精确匹配 > 模糊匹配）
    rules = [
        # Cookie 相关
        (lambda: '-101' in error_message or '账号未登录' in error_message, 'AUTH-001'),
        (lambda: '-509' in error_message or '请求过于频繁' in error_message, 'AUTH-002'),
        (lambda: 'sessdata' in msg_lower and ('expir' in msg_lower or '过期' in error_message or 'invalid' in msg_lower), 'COOKIE-001'),
        (lambda: 'sessdata' in msg_lower and ('missing' in msg_lower or '缺少' in error_message or 'not found' in msg_lower), 'COOKIE-002'),
        (lambda: 'cookie' in msg_lower and ('format' in msg_lower or '格式' in error_message or 'malformed' in msg_lower or 'parse' in msg_lower), 'COOKIE-003'),
        (lambda: context.get('http_status') == 412 or '412' in error_message, 'API-004'),

        # 网络相关
        (lambda: 'timeout' in msg_lower or 'timed out' in msg_lower or '超时' in error_message, 'NET-001'),
        (lambda: 'dns' in msg_lower or 'getaddrinfo' in msg_lower or 'name or service not known' in msg_lower or 'nodename nor servname' in msg_lower, 'NET-002'),
        (lambda: 'ssl' in msg_lower or 'certificate' in msg_lower or 'ssl3' in msg_lower or 'tls' in msg_lower, 'NET-003'),
        (lambda: 'connection refused' in msg_lower or '拒绝连接' in error_message or 'errno 61' in msg_lower or 'errno 111' in msg_lower, 'NET-004'),

        # 数据/API 相关
        (lambda: '未找到收藏夹' in error_message or 'folder' in msg_lower and 'empty' in msg_lower, 'API-001'),
        (lambda: 'json' in msg_lower and ('decode' in msg_lower or 'parse' in msg_lower or 'expecting value' in msg_lower), 'DATA-001'),
        (lambda: 'keyerror' in msg_lower or '字段缺失' in error_message or 'missing field' in msg_lower, 'DATA-002'),

        # 存储相关
        (lambda: 'no space' in msg_lower or 'disk' in msg_lower or '空间不足' in error_message or 'enospc' in msg_lower, 'STORE-001'),
        (lambda: 'permission denied' in msg_lower or '权限' in error_message or 'access is denied' in msg_lower or 'eacces' in msg_lower, 'STORE-002'),

        # 下载相关
        (lambda: '封面' in error_message and ('下载' in error_message or '失败' in error_message), 'DOWN-001'),
        (lambda: '头像' in error_message and ('下载' in error_message or '失败' in error_message), 'DOWN-002'),

        # API 通用错误
        (lambda: 'api错误' in error_message or 'api error' in msg_lower, 'API-003'),
        (lambda: '收藏夹' in error_message and '失败' in error_message, 'API-002'),
    ]

    for condition, code in rules:
        try:
            if condition():
                for err in ERROR_KB:
                    if err.code == code:
                        return err
        except Exception:
            continue

    # 默认返回未知错误
    for err in ERROR_KB:
        if err.code == 'SYS-001':
            err.message = error_message[:200]
            return err

    return None


def get_all_errors():
    """获取所有错误类型（用于模拟/演示）"""
    return ERROR_KB


def get_error_by_code(code: str) -> CrawlError:
    """按错误码查找"""
    for err in ERROR_KB:
        if err.code == code:
            return err
    return None
