# TranslateSRT-By-DeepSeek
Auto Click Continue Button, hook response function to receive dialog content, write to .md file

## python enviroment:

pip install playwright

## need pre-install chrome browser in 
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

## also you can change the define in .py file


## run cmd:
python translate_srt.py

## self-define prompt:
提示词.txt

## function:
1. auto open the chrome
2. auto open the page https://chat.deepseek.com/
3. login ds by your self
4. finished login you will get the console output infomation for your self info
5. 

## console output sample just like below:
💡 监控中... 发现“继续生成”按钮时会自动点击。
📝 正在自动填充提示词...
🎯 已检测到智能搜索开启，执行点击关闭
👤 用户信息解析成功:
   ID: ******************************
   昵称: ************
   手机: ************
身份验证成功，已更新Auth.json
🎯 发现按钮，执行点击...
[15:06:36] [📊 Token总消耗: 54146] 🎯 发现按钮，执行点击...
[15:09:14] [📊 Token总消耗: 62328] 🎯 发现按钮，执行点击...
[15:12:02] [📊 Token总消耗: 70519] 🎯 发现按钮，执行点击...
[15:14:49] [📊 Token总消耗: 78705] 🎯 发现按钮，执行点击...
[15:17:40] [📊 Token总消耗: 86896] 🎯 发现按钮，执行点击...
[15:20:32] [📊 Token总消耗: 95087] 🎯 发现按钮，执行点击...
[15:23:46] [📊 Token总消耗: 104694]
✅ 检测到 FINISHED 状态，准备保存并退出...

🛑 程序停止 (原因: KeyboardInterrupt)
✨ 运行结束。
