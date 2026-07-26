import os
import time
import json
import urllib.request
import urllib.parse
import re
from seleniumbase import SB

_account = os.environ["MINESTRATOR_ACCOUNT"].split(",")
EMAIL      = _account[0].strip()
PASSWORD   = _account[1].strip()
SERVER_ID  = os.environ.get("MINESTRATOR_SERVER_ID", "").strip()
AUTH_TOKEN = os.environ.get("MINESTRATOR_AUTH", "").strip()

_proxy = os.environ.get("GOST_PROXY", "").strip()
LOCAL_PROXY = "http://127.0.0.1:8080" if _proxy else None

_tg = os.environ.get("TG_BOT", "").strip()
TG_CHAT_ID = _tg.split(",")[0].strip() if _tg else ""
TG_TOKEN   = _tg.split(",")[1].strip() if _tg and "," in _tg else ""

LOGIN_URL  = "https://minestrator.com/connexion"
SERVER_URL = f"https://minestrator.com/my/server/{SERVER_ID}"
API_URL    = f"https://mine.sttr.io/server/{SERVER_ID}/poweraction"

# ============================================================
# TG 推送（可选）
# ============================================================

def now_str():
    import datetime
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def send_tg(result, detail=''):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT，跳过推送")
        return
    msg = (
        f"🎮 Minestrator 重启通知\n"
        f"🕐 运行时间: {now_str()}\n"
        f"🖥 服务器: 🇫🇷 Minestrator-FR\n"
        f"📊 结果: {result}\n"
        f"{detail}"
    )
    url  = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": msg}).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15):
            print("📨 TG推送成功")
    except Exception as e:
        print(f"⚠️ TG推送失败：{e}")


# ============================================================
# Invisible Turnstile：注入监听器，轮询等待 token
# ============================================================

INJECT_TOKEN_LISTENER_JS = """
(function() {
    if (window.__cf_token_listener_injected__) return;
    window.__cf_token_listener_injected__ = true;
    window.__cf_turnstile_token__ = '';

    window.addEventListener('message', function(e) {
        if (!e.origin || e.origin.indexOf('cloudflare.com') === -1) return;
        var d = e.data;
        if (!d || d.event !== 'complete' || !d.token) return;

        console.log('[TokenCapture] complete, token length:', d.token.length);
        window.__cf_turnstile_token__ = d.token;

        var inputs = document.querySelectorAll(
            'input[name="cf-turnstile-response"], input[name="cf_turnstile_response"]'
        );
        for (var i = 0; i < inputs.length; i++) {
            try {
                var nativeSet = Object.getOwnPropertyDescriptor(
                    HTMLInputElement.prototype, 'value'
                ).set;
                nativeSet.call(inputs[i], d.token);
                inputs[i].dispatchEvent(new Event('input',  {bubbles: true}));
                inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
            } catch(err) {
                inputs[i].value = d.token;
            }
        }
    });
    console.log('[TokenCapture] listener injected');
})();
"""

READ_TOKEN_JS = "(function(){ return window.__cf_turnstile_token__ || ''; })()"


def inject_listener(sb):
    try:
        sb.execute_script(INJECT_TOKEN_LISTENER_JS)
        print("📡 Turnstile 监听器已注入")
    except Exception as e:
        print(f"⚠️ 监听器注入失败：{e}")


def wait_for_token(sb, timeout=60) -> str:
    print(f"⏳ 等待 Turnstile Token 自动生成（最多 {timeout} 秒）...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            token = sb.execute_script(READ_TOKEN_JS)
            if token and len(token) > 50:
                print(f"✅ Token 已捕获（长度 {len(token)}）")
                return token
        except Exception:
            pass
        try:
            token = sb.execute_script("""
                (function(){
                    var inp = document.querySelector('input[name="cf-turnstile-response"]');
                    return (inp && inp.value && inp.value.length > 50) ? inp.value : '';
                })()
            """)
            if token:
                print(f"✅ Token 从 input 读取（长度 {len(token)}）")
                return token
        except Exception:
            pass
        time.sleep(1)

    print("❌ 等待 Token 超时")
    return ''


# ============================================================
# API：通过浏览器 fetch 发送重启指令（携带登录 Cookie）
# ============================================================

def send_restart(sb, token: str) -> bool:
    token_js = json.dumps(token)
    script = (
        "var done = arguments[0];"
        'fetch("' + API_URL + '", {'
        '  method: "PUT",'
        '  headers: {'
        '    "Authorization": "' + AUTH_TOKEN + '",'
        '    "Content-Type": "application/json",'
        '    "Accept": "application/json",'
        '    "X-Requested-With": "XMLHttpRequest"'
        '  },'
        '  body: JSON.stringify({poweraction: "restart", turnstile_token: ' + token_js + '})'
        '})'
        '.then(function(r){ return r.json(); })'
        '.then(function(data){ done({ok: true, data: data}); })'
        '.catch(function(err){ done({ok: false, error: err.toString()}); });'
    )
    try:
        result = sb.execute_async_script(script)
        print(f"📡 API响应：{result}")
        if result.get("ok") and result.get("data", {}).get("api", {}).get("code") == 200:
            print("✅ 重启指令已成功送达！")
            return True
        print(f"❌ API返回异常：{result}")
        return False
    except Exception as e:
        print(f"⚠️ API请求异常：{e}")
        return False


# ============================================================
# 主流程
# ============================================================

def run_script():
    print("🔧 启动浏览器...")

    sb_kwargs = dict(uc=True, test=True)
    if LOCAL_PROXY:
        sb_kwargs["proxy"] = LOCAL_PROXY
        print(f"🌐 使用代理：{LOCAL_PROXY}")
    else:
        print("ℹ️ 未配置代理，直连运行")

    with SB(**sb_kwargs) as sb:
        print("🚀 浏览器就绪！")

        # ── IP 验证 ──────────────────────────────────────────
        print("🌐 验证出口IP...")
        try:
            sb.open("https://api.ipify.org/?format=json")
            ip_text = re.sub(r'(\d+\.\d+\.\d+\.)\d+', r'\1xx', sb.get_text('body'))
            print(f"✅ 出口IP确认：{ip_text}")
        except Exception:
            print("⚠️ IP验证超时，跳过")

        # ── 登录 ─────────────────────────────────────────────
        print("🔑 打开登录页面...")
        sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=4)
        time.sleep(3)

        print("✏️ 填写账号密码...")
        try:
            sb.wait_for_element_visible("input[type='text']", timeout=20)
            
            # 正常填写内容
            sb.type("input[type='text']", EMAIL)
            sb.type("input[type='password']", PASSWORD)
            
            # 🔥 关键修复点：强制触发原生 input 事件，唤醒 Vue/React 框架的状态同步
            sb.execute_script("""
                var ev = new Event('input', { bubbles: true });
                document.querySelector("input[type='text']").dispatchEvent(ev);
                document.querySelector("input[type='password']").dispatchEvent(ev);
            """)
            time.sleep(1) # 给前端框架 1 秒钟处理状态
            
            try:
                sb.execute_script("var r=document.querySelector('input[type=\"checkbox\"]'); if(r) r.checked=true;")
            except Exception:
                pass
        except Exception:
            print("❌ 登录框加载失败")
            sb.save_screenshot("login_fail.png")
            return

        print("📤 提交登录请求...")
        try:
            # 绝招 1：在密码框里直接发送“回车键 (\n)”，触发表单的原生提交（最稳妥！）
            sb.press_keys("input[type='password']", "\n")
            time.sleep(2)
            
            # 绝招 2：备用兜底，万一回车没生效，用 JS 原生冒泡事件强行点那颗绿色的按钮
            sb.execute_script("""
                let btns = document.querySelectorAll('button');
                for (let i = 0; i < btns.length; i++) {
                    let b = btns[i];
                    if (b.innerText.includes('Se connecter') || b.type === 'submit') {
                        b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        break;
                    }
                }
            """)
        except Exception as e:
            print(f"⚠️ 登录提交辅助触发异常 (不影响大局): {e}")

        print("⏳ 等待登录跳转...")
        for _ in range(40):
            try:
                if "/connexion" not in sb.get_current_url():
                    print(f"✅ 登录成功！当前页：{sb.get_current_url()}")
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            print("❌ 登录等待超时")
            sb.save_screenshot("login_timeout.png")
            return

        # ── 跳转服务器管理页 ──────────────────────────────────
        print(f"🔃 跳转至服务器管理页：{SERVER_URL}")
        sb.open(SERVER_URL)
        
        # ── 等待面板加载完成 ──────────────────────────────────
        print("⏳ 等待服务器面板加载 (约需 15 秒)...")
        # 页面会有加载圈 (image_7)，我们等待终端控制台或状态字样出现 (image_8)
        try:
            sb.wait_for_element_visible("div.font-mono, #console, .terminal, button", timeout=30)
            print("✅ 面板 UI 加载成功！")
            time.sleep(5) # 额外缓冲 5 秒，确保按钮完全渲染并绑定了点击事件
        except Exception:
            print("⚠️ 未能精准检测到控制台特征，执行硬等待...")
            time.sleep(20)
            
        # ── 点击重启按钮（真实鼠标点击 + MouseEvent 双重保障） ────────
        print("🔄 寻找并执行真实物理点击蓝色【重启】按钮...")
        try:
            # 1. 派发完整的 MouseEvent 冒泡事件，强行唤醒 Vue/React 事件监听器
            js_clicked = sb.execute_script("""
                return (function() {
                    let btns = document.querySelectorAll('button');
                    for (let i = 0; i < btns.length; i++) {
                        let b = btns[i];
                        let style = window.getComputedStyle(b);
                        // 匹配蓝色且带有 svg 的按钮
                        if (b.querySelector('svg') && (style.backgroundColor.includes('blue') || style.backgroundColor.includes('rgb(37, 99, 235)') || style.backgroundColor.includes('rgb(59, 130, 246)'))) {
                            // 构造并派发真实的 MouseEvent 冒泡事件
                            let mouseEvt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                            b.dispatchEvent(mouseEvt);
                            
                            // 同时对内部的 svg 也触发一次，双重保险
                            let svg = b.querySelector('svg');
                            if (svg) svg.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                            return true;
                        }
                    }
                    return false;
                })();
            """)

            # 2. 结合 SeleniumBase 原生物理点击 (模拟真实鼠标光标移动 + Hover + 物理按下)
            try:
                # 匹配面板上的蓝色按钮或第一个图标按钮
                button_xpath = "//button[contains(@class,'blue') or contains(@class,'primary') or .//svg][1]"
                if sb.is_element_visible(button_xpath):
                    sb.scroll_to_element(button_xpath)
                    time.sleep(0.5)
                    sb.click(button_xpath)  # 物理鼠标点击
                    print("✅ 已触发 SeleniumBase 原生物理鼠标点击！")
            except Exception as pe:
                print(f"⚠️ 物理点击辅助触发: {pe}")

            print("⏳ 重启指令已发送，等待后台响应 (10 秒)...")
            time.sleep(10)
            
            # 3. 刷新页面，验证倒计时是否真正重置为 3h 59m
            print("🔄 刷新页面以验证倒计时重置效果...")
            sb.refresh()
            time.sleep(5)
            
            # 截图保存，方便在 GitHub Actions 的 Artifacts 里直接验证
            sb.save_screenshot("after_restart.png")
            print("📸 已保存点击后的验证截图 (after_restart.png)")
            
            send_tg("✅ 保活执行完成", "已触发真实物理点击，已刷新并保存验证截图")

        except Exception as e:
            print(f"❌ 按钮点击异常: {e}")
            sb.save_screenshot("button_error.png")
            send_tg("❌ 保活执行失败", "点击异常，请检查截图")

if __name__ == "__main__":
    run_script()
