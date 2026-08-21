# CC 消息配置

在项目根目录 `.env` 或部署环境中设置：

```dotenv
CC_MSG_LOGIN_URL=https://your-cc-login-url.com/api/login
CC_MSG_SEND_URL=https://your-cc-send-url.com/api/send
CC_MSG_USERNAME=your_username
CC_MSG_PASSWORD=your_password
```

配置说明：

| 变量 | 说明 |
| --- | --- |
| `CC_MSG_LOGIN_URL` | CC 登录接口 URL |
| `CC_MSG_SEND_URL` | CC 消息发送接口 URL |
| `CC_MSG_USERNAME` | CC 登录用户名，同时作为发送者 ID |
| `CC_MSG_PASSWORD` | CC 登录密码 |

CC 消息正文使用以下协议标签拼接：

```text
[banner_img_B]{url}[banner_img_E]
[title_B]{标题}[title_E]
[version_B]2[version_E]
{消息正文}
[url_B]{图片 URL}[url_E]
[issso_B]false[issso_E]
[param_B][param_E]
[url_show_B]{显示文本}[url_show_E]
```

不要把真实 URL、用户名或密码提交到仓库。
