# pdu-control

[English](README.md) | 简体中文

在局域网内控制 UniFi Power Distribution Pro（USP-PDU-Pro）的命令行脚本。通过 UniFi OS 控制台（如 UCG-Fiber）内置 Network 应用的本地 API 操作，不经过 Ubiquiti 云。

需要 Python 3.14 及以上版本，只依赖标准库，无需安装第三方包。

> 注意：脚本使用的是 UniFi Network 的非官方本地 API，尚未在真实设备上完整验证，固件升级后接口可能变化。

## 安装

### Python 版本

要求 **Python 3.14 及以上**。先确认当前版本：

```bash
python3 --version
```

如果低于 3.14，可以任选一种方式安装：

```bash
# 使用 uv（跨平台，推荐）
uv python install 3.14
uv run --python 3.14 ./pdu.py list

# 使用 pyenv
pyenv install 3.14
pyenv local 3.14

# Fedora
sudo dnf install python3.14

# macOS（Homebrew）
brew install python@3.14
```

Windows 可从 [python.org](https://www.python.org/downloads/) 下载 3.14 安装包。

### 依赖

脚本只使用 Python 标准库（`urllib`、`http.cookiejar`、`ssl`、`json`、`argparse` 等），**无需 `pip install` 任何第三方包**，也不需要虚拟环境。

### 获取脚本

```bash
git clone <仓库地址> pdu-control
cd pdu-control
chmod +x pdu.py
```

如果系统默认的 `python3` 不是 3.14+，可以用指定解释器直接运行：

```bash
python3.14 ./pdu.py list
```

## 前提条件

- PDU Pro 已被局域网内的 UniFi 控制台（UCG-Fiber、UDM 等）接管
- 运行脚本的机器能访问控制台的 HTTPS 端口
- 控制台上有一个**本地账号**（不能用 Ubiquiti 云/SSO 账号），权限见下文

创建本地账号：UniFi OS → Admins & Users → 添加管理员，选择 "Restrict to local access only"，并为 Network 应用分配合适的角色。

## 账号权限

脚本只需要 Network 应用的权限，不需要 UniFi OS 超级管理员/所有者，也不需要 Protect、Access 等其他应用的权限。

| 操作 | 所需权限 |
| --- | --- |
| `list`（查看插座状态、功率） | Network 只读（View Only）理论上即可 |
| `on` / `off` / `cycle`（开关插座） | Network 管理权限 |

开关插座是通过 `PUT rest/device/<id>` 修改设备的 `outlet_overrides` 实现的，属于写操作，只读账号会返回 401/403。

不同 UniFi OS 版本的 Network 角色名称和粒度不同，介于只读和完全管理之间的受限角色能否开关插座尚未验证。建议按最小权限原则：

1. 先用只读账号运行 `./pdu.py list`，仅监控时就用它
2. 需要开关时，从最低的可写角色开始，用一个不重要的插座测试 `off` / `on`，遇到 403 再逐级提升

建议为脚本单独建账号，不要使用个人主账号，便于单独吊销和审计。

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

### 使用 `.env` 文件

也可以不手动 export，而是复制模板并填入真实值：

```bash
cp .env.example .env
# 编辑 .env：填写 UNIFI_HOST、UNIFI_USER、UNIFI_PASS
```

脚本不会自动读取 `.env`，运行前需要先加载到当前 shell：

```bash
set -a; source .env; set +a
./pdu.py list
```

`.env` 已加入 `.gitignore`，不会被提交到 git；仓库中只保存不含真实密码的 `.env.example`。

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
