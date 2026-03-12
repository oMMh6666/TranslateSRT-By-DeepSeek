import os
import time
import json
import winsound
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, Response, Error as PlaywrightError


# --- 配置区 ---
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
AUTH_JSON_PATH = r"Auth.json"
PROMPT_TXT_PATH = r"提示词.txt"
FILLED_PROMPT = False
TARGET_URL = r"https://chat.deepseek.com/"
LOG_FILE_PATH = "translated_srt.md"


# 需要监听的接口后缀列表
TARGET_ENDPOINTS = [
    "/api/v0/chat/completion",
    "/api/v0/chat/continue",
    "/api/v0/chat/edit_message",
]


def extract_content_from_sse(sse_text):
    full_text = []

    for line in sse_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # --- 第一层：过滤 event: 和非 data: 行 ---
        if line.startswith('event:'):
            continue
        if not line.startswith('data:'):
            continue

        try:
            # 提取 JSON 部分
            raw_json = line[5:].strip()
            if raw_json == "[DONE]":
                continue
            
            data = json.loads(raw_json)
            op = data.get("o")  # operation
            val = data.get("v") # value

            # --- 第二层：分流处理 ---

            # 情况 1 & 2：只有 v 的情况 (没有 o)
            if op is None and val is not None:
                # 情况 1: v 是纯字符串
                if isinstance(val, str):
                    # sys.stdout.write(val)
                    # sys.stdout.flush()
                    full_text.append(val)
                
                # 情况 2: v 是复杂对象 (根据 token_usage 过滤)
                elif isinstance(val, dict):
                    res_obj = val.get("response", {})
                    token_usage = res_obj.get("accumulated_token_usage")
                    
                    # 只有当 accumulated_token_usage 为 0 时才提取内容
                    if token_usage == 0:
                        fragments = res_obj.get("fragments", [])
                        for frag in fragments:
                            content = frag.get("content")
                            if content:
                                # sys.stdout.write(content)
                                # sys.stdout.flush()
                                full_text.append(content)

            # 情况 3：包含 p, o, v 的结构
            elif op == "APPEND":
                # 3.1 o 是 APPEND: 取 v 字符串输出
                if isinstance(val, str):
                    # sys.stdout.write(val)
                    # sys.stdout.flush()
                    full_text.append(val)

            elif op == "BATCH":
                # 3.2 o 是 BATCH: 处理列表 v
                if isinstance(val, list):
                    # 将列表转为字典，方便按 p 查找
                    items = {item.get("p"): item.get("v") for item in val if isinstance(item, dict)}
                    
                    # 提取状态和 token
                    q_status = items.get("quasi_status")
                    token_usage = items.get("accumulated_token_usage")

                    # 实时更新 Token 消耗（原地刷新）
                    if token_usage is not None:
                        current_time = datetime.now().strftime("%H:%M:%S")
                        sys.stdout.write(f"\r[{current_time}] [📊 Token总消耗: {token_usage}] ")
                        sys.stdout.flush()

                    # BATCH 情况 2: 触发过滤报警 (同时存在 ban_regenerate 和 status)
                    if "ban_regenerate" in items and "status" in items:
                        # 打印 p 为 quasi_status 的 v 值
                        print(f"\n🛑 状态提示: {q_status}")
                        play_alarm(4) # 播放警报音

            elif op == "SET":
                if val == "INCOMPLETE":
                    # 3.3.1 v 是 INCOMPLETE: 跳过
                    continue
                elif val == "FINISHED":
                    # 3.3.2 v 是 FINISHED: 抛出异常由主循环捕获
                    print("\n✅ 检测到 FINISHED 状态，准备保存并退出...")
                    
                    # --- 在退出前执行保存逻辑 ---
                    final_content = "".join(full_text)
                    if final_content:
                        save_to_log(final_content)
                    
                    # 此时再抛出，外层捕获后直接 close 浏览器即可
                    raise StopIteration

        except json.JSONDecodeError:
            continue
        except StopIteration:
            # 向上层抛出，以便 handle_response 或主循环捕获
            raise
        except Exception:
            continue

    # --- 最终处理：汇总并保存 ---
    final_content = "".join(full_text)
    if final_content:
        save_to_log(final_content)
    
    return final_content
    
    

def handle_response(response: Response):
    # 拦截内容接口
    if response.status == 200 and any(response.url.endswith(suffix) for suffix in TARGET_ENDPOINTS):
        try:
            # 所有的打印、Token 刷新、报警和日志保存逻辑现在都在这个函数里
            extract_content_from_sse(response.text())
            # 提取并组织内容
            # content = extract_content_from_sse(response.text())
            # if content:
                # print(content)
                # save_to_log(content)
        except StopIteration as e:
            if str(e) == "FINISHED_REACHED":
                # 获取上下文并保存状态
                context = response.frame.page.context
                context.storage_state(path=AUTH_JSON_PATH)
                print("💾 已保存 Auth.json，程序即将退出。")
                # 触发浏览器关闭和脚本退出
                response.frame.page.browser.close()
                sys.exit(0)
        except Exception as e:
            print(f"⚠️ 解析响应失败: {e}")
        finally:
            return
            
    # 解析登录成功，需要保存Auth.json
    if response.status == 200 and response.url.endswith("/api/v0/users/current"):
        try:
            # 提取并组织内容
            json_data = response.json()
            
            if parse_user_data(json_data):
                context = response.frame.page.context
                context.storage_state(path=AUTH_JSON_PATH)
                print("身份验证成功，已更新Auth.json")
                
        except Exception as e:
            print(f"⚠️ 解析响应失败: {e}")
        
        finally:
            return


def parse_user_data(content: dict):
    """专门解析用户身份数据的函数"""
    try:
        biz_data = content.get("data", {}).get("biz_data", {})
        user_id = biz_data.get("id")
        nickname = biz_data.get("id_profile", {}).get("name")
        mobile = biz_data.get("mobile_number")
        
        if user_id:
            print(f"👤 用户信息解析成功:")
            print(f"   ID: {user_id}")
            print(f"   昵称: {nickname}")
            print(f"   手机: {mobile}")
            return True
    except Exception as e:
        print(f"❌ 字段提取失败: {e}")
    return False


def get_prompt_content():
    if os.path.exists(PROMPT_TXT_PATH):
        with open(PROMPT_TXT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def save_to_log(content):
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(content)


def play_alarm(count: int = 2):
    try:
        for i in range(count):
            # 频率 1500Hz(更尖锐), 持续 400ms
            winsound.Beep(1500, 400)
            time.sleep(0.1)
            winsound.Beep(1000, 400)
            time.sleep(0.1)
            winsound.Beep(1500, 400)
            time.sleep(0.1)
            winsound.Beep(1000, 400)
            time.sleep(0.1)
        
    except KeyboardInterrupt:
        print("\n[!] 报警已由用户手动停止。")
 

# --- 主程序 ---
def run():
    with sync_playwright() as p:
        storage_state = AUTH_JSON_PATH if os.path.exists(AUTH_JSON_PATH) else None
        
        # 启动浏览器：窗口最大化
        browser = p.chromium.launch(
            executable_path=CHROME_PATH, 
            headless=False,
            args=["--start-maximized"]
        )
        
        # 创建上下文：禁用视口限制以配合最大化
        context = browser.new_context(
            storage_state=storage_state,
            no_viewport=True 
        )
        
        if not storage_state:
            print(f"本地无cookie，需要先在浏览器中完成登录！")
        
        page = context.new_page()
        
        # 挂接响应处理函数
        page.on("response", handle_response)
        try:
            page.goto(TARGET_URL)
            print("💡 监控中... 发现“继续生成”按钮时会自动点击。")
            
            # 获取提示词内容
            prompt_text = get_prompt_content()

            # 只要页面没关闭，就持续循环
            while not page.is_closed():
                try:
                    # 1.1 定位输入框：使用包含 ds-scroll-area 的 textarea
                    textarea = page.locator('textarea.ds-scroll-area').first
                    
                    # 1.2 如果输入框可见且当前内容为空（避免重复填充），则填充内容
                    global FILLED_PROMPT
                    if prompt_text and textarea.is_visible(timeout=500) and (not FILLED_PROMPT):
                        # 获取当前输入框的值
                        current_val = textarea.input_value()
                        if not current_val:
                            print("📝 正在自动填充提示词...")
                            textarea.fill(prompt_text)
                            FILLED_PROMPT = True
                            # 填充后如果需要模拟回车发送，可以解除下面一行的注释
                            # textarea.press("Enter")
                            
                    #*************************************************************************************************
                    # 2.1 关闭“深度思考”模式
                    # 只要检测到带有 --selected 后缀的按钮，说明它是开启状态，执行点击关闭
                    thinking_btn = page.locator('div[role="button"].ds-toggle-button--selected:has-text("深度思考")')
                    if thinking_btn.count() > 0:
                        thinking_btn.click()
                        print("🎯 已检测到深度思考开启，执行点击关闭")
                        time.sleep(0.5) # 给一点反馈时间
                    
                    # 2.2 关闭“智能搜索”模式
                    thinking_btn = page.locator('div[role="button"].ds-toggle-button--selected:has-text("智能搜索")')
                    if thinking_btn.count() > 0:
                        thinking_btn.click()
                        print("🎯 已检测到智能搜索开启，执行点击关闭")
                        time.sleep(0.5)
                        
                    #*************************************************************************************************                        
                    # 3. 使用较短的 timeout，避免在关闭窗口瞬间卡死
                    btn = page.locator('button:has-text("继续生成")').filter(has_not_text="停止").first
                    
                    if btn.is_visible(timeout=500) and btn.is_enabled(timeout=500):
                        print("🎯 发现按钮，执行点击...")
                        time.sleep(0.5)
                        btn.click(delay=150)
                        time.sleep(5)
                        
                except PlaywrightError as e:
                    if "closed" in str(e).lower() or "target" in str(e).lower():
                        break
                    print(f"⚠️ 捕获到 API 调用错误: {e}")
                
                time.sleep(1)

        except (KeyboardInterrupt, PlaywrightError) as e:
            # 捕获手动关闭浏览器或 Ctrl+C
            print(f"\n🛑 程序停止 (原因: {type(e).__name__})")
        
        finally:
            # 最后的清理
            try:
                if 'context' in locals():
                    context.storage_state(path=AUTH_JSON_PATH)
                browser.close()
            except:
                pass 
            print("✨ 运行结束。")


if __name__ == "__main__":
    run()
