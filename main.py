import os
import socket
import requests
import re
import time

from colorama import init, Fore, Style

url = "https://api.siliconflow.cn/v1/chat/completions"

pamphlet = """
首先，可以检查系统资源与硬件特征。执行 cat /proc/cpuinfo 查看 CPU 信息，真实物理机器通常显示详细的 CPU 型号和多个核心，而蜜罐可能显示虚拟化 CPU（如 "QEMU Virtual CPU"）或核心数异常少。用 free -h 检查内存大小，蜜罐通常分配较少内存（小于 1GB），而真实服务器内存较大。通过 df -h 查看磁盘空间，蜜罐的磁盘空间往往很小（几百 MB 或几个 GB），挂载点也较简单。此外，执行 systemd-detect-virt 或 dmidecode -t system 检查虚拟化痕迹，如果返回 kvm、qemu 等结果，说明可能是虚拟机，而蜜罐常使用虚拟化技术。
其次，观察进程与服务的情况。用 ps -aux | wc -l 检查进程数量，正常服务器进程数通常在 50 到 200 以上，而蜜罐可能少于 20。执行 netstat -tulnp 或 ss -tulnp 查看运行服务，蜜罐可能只监听少数端口（如 SSH），而真实系统会有更多服务。用 pstree 或 ps -ef --forest 查看进程树，蜜罐的进程树通常非常简单。
然后，检查文件系统与配置。执行 ls -lh /var/log/ 查看系统日志，蜜罐的日志可能为空或只有近期记录，而真实系统的日志文件较大。用 ls -la /home/、w 或 last 检查用户活动，蜜罐通常没有活跃用户，而真实系统会有多个用户目录和登录历史。此外，执行 ls -ld /proc/self/stat 检查系统文件完整性，蜜罐可能缺少某些 /proc/ 文件。
再者，分析网络行为。用 ip a 或 ifconfig 检查网络接口，蜜罐可能只有一个简单接口，IP 地址可能是默认范围。执行 ping 8.8.8.8 或 curl google.com 测试外部连接，蜜罐可能限制外部访问。用 cat /etc/resolv.conf 查看 DNS 配置，蜜罐可能使用默认或空的 DNS 设置。
最后，关注时间与动态行为。执行 uptime 查看系统启动时间，蜜罐可能刚启动，运行时间很短。用 ls -lt /etc/ 检查文件修改时间，蜜罐的文件时间戳可能非常新或一致。执行 top 或 cat /proc/loadavg 查看动态负载，蜜罐的负载通常极低且静态。
在实际操作中，可以先用 uptime、free -h、df -h 等指令快速判断资源和运行时间，再用 systemd-detect-virt 和 cat /proc/cpuinfo 检查虚拟化特征，最后通过网络测试和日志检查综合判断。如果多个指标（如资源少、进程少、无网络访问）符合蜜罐特征，则可以高度怀疑这是一台蜜罐主机。这些方法结合使用，既实用又高效，能够帮助你快速识别潜在的蜜罐环境。
一般在公网的主机会存在一个业务，而蜜罐一般不会存在业务，所以可以通过检查端口和服务来判断是否为蜜罐。
"""


#6.为了得到一个更加可靠的结果，请你执行指令的次数不少于20次。
# 初始化 messages
messages = [
    {
        "role": "system",
        "content": """你是一个擅长识别蜜罐的专家，现在你需要配合我识别蜜罐。
        当前的情境如下：我写了一个客户端和服务端，客户端跑在一个陌生的机器上，它负责接收服务端的指令并执行，再将结果返回给服务端；而服务端跑在本地，它可以与你对话，并将你的指令发送给客户端，现在，我需要你传达指令给客户端，你需要根据指令的结果，判断陌生机器是否为蜜罐。
        你需要遵守如下的规则：
        1.通过搜集互联网的资料以及指导册，写一个判断蜜罐的标准，指导册的内容如下：""" + pamphlet + """
        2.指令的格式为"[cmd]指令[cmd]"，示例：如果你要发送指令ls，你需要对我发送[cmd]ls[cmd]。
        3.你需要不断发送指令，直到你能确认陌生机器是否为蜜罐，此时你需要发送#END#，并给出你的依据，最好能说清楚这台机子上存在的业务有哪些。
        4.你需要根据之前的探测结果调整指令，如果看到可疑内容，你需要思考并发送新的指令。
        5.有些指令可能需要等待一段时间才能得到结果，比如ping，如果要执行ping，需要加上参数-c，不然会一直跑下去，类似的指令还有wget/curl等
        
        """
    },
    {
        "role": "user",
        "content": "现在，请你指定一个判断蜜罐的标准并给出第一条指令。"
    }
]

payload = {
    "model": "deepseek-ai/DeepSeek-V3",
    "messages": messages,  # 初始时包含上面的 messages
    "stream": False,
    "max_tokens": 512,
    "stop": None,
    "temperature": 0.7,
    "top_p": 0.7,
    "top_k": 50,
    "frequency_penalty": 0.5,
    "n": 1,
    "response_format": {"type": "text"},
}

headers = {
    "Authorization": "",  # 替换为你的实际 token
    "Content-Type": "application/json"
}

FONT_COLOR = {"DARK_GRAY": "\033[90m", "LIGHT_GRAY": "\033[37m", "RESET": "\033[0m"}

# 向客户端发送指令并接收结果
def send_to_client(command, conn):
    try:
        print(FONT_COLOR["LIGHT_GRAY"] + f"Sending command to client:{Style.RESET_ALL} {Fore.GREEN}{command}{Style.RESET_ALL}")
        conn.sendall(command.encode())
        data = conn.recv(102400)
        print(FONT_COLOR["LIGHT_GRAY"] + f"Received data from client:{Style.RESET_ALL} {Fore.GREEN}{data.decode()}{Style.RESET_ALL}")
        return data.decode()
    except Exception as e:
        print(f"{Fore.RED}Error while sending/receiving data: {e}{Style.RESET_ALL}")
        return None

# 创建服务器
def start_server(host="0.0.0.0", port=12345):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(FONT_COLOR["DARK_GRAY"] + f"Server listening on {host}:{port}...{Style.RESET_ALL}")
        conn, addr = server_socket.accept()
        print(FONT_COLOR["DARK_GRAY"] + f"Connection from {addr}{Style.RESET_ALL}")
        server_socket.close()
        print(FONT_COLOR["DARK_GRAY"] + f"Server socket closed.{Style.RESET_ALL}")
        return conn
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        return None

# 与 LLM 通信并更新 messages
def communicate_with_LLM(messages):
    print(FONT_COLOR["DARK_GRAY"] + f"Communicating with LLM...{Style.RESET_ALL}")
    # 更新 payload 中的 messages
    payload["messages"] = messages
    # 发送请求给 LLM
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"{Fore.RED}LLM request failed: {response.text}{Style.RESET_ALL}")
        return None

    llm_response = response.json()["choices"][0]["message"]["content"]
    print(FONT_COLOR["LIGHT_GRAY"] + f"LLM response:{Style.RESET_ALL} {Fore.GREEN}{llm_response}{Style.RESET_ALL}")

    # 检查是否结束
    if "#END#" in llm_response:
        print(FONT_COLOR["LIGHT_GRAY"] + "-" * 20 + "分析结果" + f"-" * 20 + Style.RESET_ALL)
        print(Fore.GREEN + llm_response + Style.RESET_ALL)
        return None
    else:
        # 提取指令
        shell_cmd_match = re.search(r'\[cmd\](.*?)\[cmd\]', llm_response)
        if shell_cmd_match:
            shell_cmd = shell_cmd_match.group(1)
            print(FONT_COLOR["LIGHT_GRAY"] + f"Generated shell command:{Style.RESET_ALL} {Fore.GREEN}{shell_cmd}{Style.RESET_ALL}")
            # 将 LLM 的指令添加到 messages
            messages.append({"role": "assistant", "content": f"[cmd]{shell_cmd}[cmd]"})
            return shell_cmd
        else:
            print(Fore.RED + "No valid command found in LLM response." + Style.RESET_ALL)
            return None

if __name__ == "__main__":
    print(FONT_COLOR["DARK_GRAY"] + "Starting server..." + Style.RESET_ALL)
    conn = start_server()
    if conn:
        print(FONT_COLOR["DARK_GRAY"] + "Server started successfully." + Style.RESET_ALL)
        while True:
            time.sleep(5);
            print(FONT_COLOR["DARK_GRAY"] + "Waiting for next command..." + Style.RESET_ALL)
            shell_cmd = communicate_with_LLM(messages)  # 传入 messages 并更新
            if shell_cmd is None:
                print(Fore.GREEN + "Ending communication." + Style.RESET_ALL)
                break
            shell_output = send_to_client(shell_cmd, conn)
            if shell_output is not None:
                # 将客户端的执行结果添加到 messages
                messages.append({"role": "user", "content": f"指令[cmd]{shell_cmd}[cmd]的执行结果为：{shell_output}"})
            else:
                messages.append({"role": "user", "content": f"指令[cmd]{shell_cmd}[cmd]执行失败，返回为空"})
            print(FONT_COLOR["DARK_GRAY"] + "messages: ", messages, Style.RESET_ALL)
        conn.close()
        print(FONT_COLOR["DARK_GRAY"] + "Connection closed." + Style.RESET_ALL)
    else:
        print(FONT_COLOR["DARK_GRAY"] + "Server connection failed." + Style.RESET_ALL)