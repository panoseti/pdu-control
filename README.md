# pdu-control

在局域网内控制 UniFi Power Distribution Pro（USP-PDU-Pro）的命令行脚本。通过 UniFi OS 控制台（如 UCG-Fiber）内置 Network 应用的本地 API 操作，不经过 Ubiquiti 云。

只依赖 Python 3 标准库，无需安装第三方包。

> 注意：脚本使用的是 UniFi Network 的非官方本地 API，尚未在真实设备上完整验证，固件升级后接口可能变化。

## 前提条件

- PDU Pro 已被局域网内的 UniFi 控制台（UCG-Fiber、UDM 等）接管
- 运行脚本的机器能访问控制台的 HTTPS 端口
- 控制台上有一个**本地账号**（不能用 Ubiquiti 云/SSO 账号），并具有 Network 应用的管理员权限

创建本地账号：UniFi OS → Admins & Users → 添加管理员，选择 "Restrict to local access only"，并为 Network 分配 Admin 角色。

## 配置

通过环境变量提供连接信息：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `UNIFI_HOST` | 控制台地址，如 `192.168.1.1` | 必填 |
| `UNIFI_USER` | 本地账号用户名 | 必填 |
| `UNIFI_PASS` | 本地账号密码 | 必填 |
| `UNIFI_SITE` | 站点名 | `default` |

```bash
export UNIFI_HOST=192.168.1.1
export UNIFI_USER=pdu-admin
export UNIFI_PASS='your-password'
```

控制台使用自签名证书，脚本默认不校验 TLS 证书。

## 用法

```bash
./pdu.py list                 # 列出所有插座的编号、状态、名称和功率
./pdu.py on 3                 # 打开 3 号插座
./pdu.py off 3                # 关闭 3 号插座
./pdu.py cycle 3              # 断电 5 秒后重新上电
./pdu.py cycle 3 --delay 10   # 自定义断电时长（秒）
```

如果控制台下接管了多个带插座的设备（例如还有 SmartPower 插座），需要用 `--mac` 指定 PDU：

```bash
./pdu.py --mac aa:bb:cc:dd:ee:ff list
```

`list` 输出示例（型号字段以控制器实际返回为准）：

```
Rack PDU  model=<型号>  mac=aa:bb:cc:dd:ee:ff
   1  ON   NAS                      42.1 W
   2  OFF  Outlet 2
   ...
```

## 注意事项

- 首次测试请选一个不重要的插座，**不要关闭给 UCG-Fiber 或交换机供电的插座**，否则网络会中断，脚本也无法再把它打开。
- `cycle` 是先关、等待、再开的两步操作；如果中途脚本被中断，插座会停留在关闭状态。
- 遇到 `HTTP 401/403` 请检查账号是否为本地账号且有 Network 管理员权限。
