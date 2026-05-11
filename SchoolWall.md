# **鄂应墙 MVP 技术实现文档 **

## Phase 1：架构底座与数据定义

### **1\. 工程架构与技术栈总览 (Architecture & Stack)**

为了保证前后端的高效协同，并为后期的异步处理留足空间，本阶段锁定以下核心技术栈与部署环境。

#### **1.1 技术栈选型**

* **前端 (Client)：**  
  * 框架：Uni-app (Vue 3 \+ Vite 体系)。  
  * 核心职责：多端编译（优先适配微信小程序）、本地 Storage 缓存（Token 与基础字典）、微信原生能力调用（登录授权、图片压缩上传）。  
* **后端 (Server)：**  
  * 框架：Python 3.10+配合 FastAPI (基于 Uvicorn 异步服务器)。  
  * 核心职责：高并发 API 响应、鉴权拦截、执行教务系统爬虫脚本、内容审核队列调度。  
* **数据层 (Data & Cache)：**  
  * 持久化：PostgreSQL 15+ (利用其稳定性和强大的 JSONB 支持)。  
  * 缓存与队列：Redis (承担高频 Token 校验、限流防刷、异步审核任务队列)。

#### **1.2 开发与部署环境规划**

* **开发环境 (Local Dev)：** 统一采用 Docker Compose 进行编排。在本地（如 WSL2 环境）一键拉起 PostgreSQL 和 Redis 容器，确保开发环境与主机系统的绝对物理隔离，保持宿主机纯净。  
* **生产环境 (Production)：** 单节点 VPS 部署，使用 Nginx 作为反向代理并卸载 HTTPS 证书（强制要求，微信 API 限制）。后端服务容器化运行。



### **2\. 核心鉴权与学籍绑定链路 (Authentication Flow)**

这是本阶段最核心的业务逻辑，必须严格遵守安全规范，特别是**绝对禁止持久化存储用户的教务系统密码**。

#### **2.1 状态转移逻辑**

1. **静默授权 (游客态)：** 用户打开小程序，前端调用 wx.login 获取 code，后端换取 openid 并生成一个具有基础权限（仅读）的 JWT 返回给前端。  
2. **发起认证 (提交表单)：** 用户填写 student\_id (学号) 和 academic\_password (教务系统密码)，通过 HTTPS 安全链路提交至后端。  
3. **鉴真与抓取 (后端爬虫执行)：** 后端 FastAPI 接收到请求后，实时调用爬虫模块向学校教务系统发起模拟登录。  
   * **失败：** 返回密码错误或系统繁忙提示。  
   * **成功：** 抓取用户的 real\_name (真实姓名)。  
4. **状态落库与凭证销毁 (关键安全点)：** 将 student\_id 和 real\_name 写入数据库的 users 表，更新验证状态 is\_verified \= True。**随后立即在内存中销毁 academic\_password 变量，绝不落库。**  
5. **权限升级：** 后端签发新的、包含已认证状态的高权限 JWT，用户解锁发帖与查看他人微信号的功能。

## 

### **3\. 数据库表结构定义 (Database Schema \- PostgreSQL)**

以下结构已针对 MVP 的“信息撮合 \+ C2C 交流”模式进行了极致精简。采用 Snake\_case 命名规范。

#### **3.1 users (用户身份与权限表)**

此表是鉴权和实名防范的核心底座。

| 字段名 (Field) | 数据类型 (Type) | 约束与索引 (Constraints) | 业务说明 (Description) |
| :---- | :---- | :---- | :---- |
| id | UUID | Primary Key, Default uuid\_generate\_v4() | 系统内部唯一标识 |
| openid | VARCHAR(64) | Unique Index, Not Null | 微信用户的 OpenID |
| student\_id | VARCHAR(20) | Unique Index, Nullable | 学号（绑定教务系统后更新） |
| real\_name | VARCHAR(50) | Nullable | 真实姓名（教务系统抓取，作为核验底单，绝不在前端公开） |
| wechat\_id | VARCHAR(50) | Nullable | **用户填写的微信号**，用于线下 C2C 交易联系 |
| avatar\_url | VARCHAR(255) | Nullable | 微信头像或默认头像 CDN 链接 |
| nickname | VARCHAR(50) | Not Null | 小程序内展示的昵称（默认为“鄂应学子\_随机码”） |
| is\_verified | BOOLEAN | Default FALSE, Index | **核心权限阀门**：是否完成学籍认证 |
| status | SMALLINT | Default 1 | 账户状态：1 正常，0 冻结（违规触发） |
| created\_at | TIMESTAMPTZ | Default CURRENT\_TIMESTAMP | 注册时间 |
| updated\_at | TIMESTAMPTZ | Default CURRENT\_TIMESTAMP | 最后更新时间 |

#### **3.2 posts (全站信息流主表)**

承载校园墙所有展示内容，利用 JSONB 处理图片，保持表结构扁平化。

| 字段名 (Field) | 数据类型 (Type) | 约束与索引 (Constraints) | 业务说明 (Description) |
| :---- | :---- | :---- | :---- |
| id | BIGSERIAL | Primary Key | 帖子自增主键 |
| user\_id | UUID | Foreign Key (users.id), Index | 发帖人 ID |
| post\_type | VARCHAR(20) | Not Null, Index | 版块类型枚举： lost\_found (失物) second\_hand (二手) carpool (拼车) general (万能墙) |
| content | TEXT | Not Null | 帖子正文（须经微信文本过滤） |
| images | JSONB | Default \[\] | 数组格式的图片 CDN 链接（限制最多 6 张） |
| price | DECIMAL(10,2) | Nullable | **价格标签**：仅在 second\_hand 类型下前端展示 |
| status | SMALLINT | Default 0, Index | 帖子可见性状态： 0: 待图片机审 1: 正常展示 2: 发帖人标记已解决/已出 \-1: 管理员/机审封禁隐藏 |
| created\_at | TIMESTAMPTZ | Default CURRENT\_TIMESTAMP, Index | 发布时间（前端信息流降序排版依据） |
| updated\_at | TIMESTAMPTZ | Default CURRENT\_TIMESTAMP | 记录更新时间（如降价修改） |

#### **3.3 tags 与 post\_tags (分类标签关联表)**

实现“高数资料”、“一食堂”等精细化维度筛选。

**表：tags (全局标签库)**

| 字段名 | 数据类型 | 约束与索引 | 业务说明 |
| :---- | :---- | :---- | :---- |
| id | SERIAL | Primary Key | 标签 ID |
| name | VARCHAR(30) | Unique Index, Not Null | 标签名称，如 \#求职辅导 |

**表：post\_tags (帖子与标签多对多映射)**

| 字段名 | 数据类型 | 约束与索引 | 业务说明 |
| :---- | :---- | :---- | :---- |
| post\_id | BIGINT | Foreign Key (posts.id), PK\_Part 1 | 关联的帖子 |
| tag\_id | INTEGER | Foreign Key (tags.id), PK\_Part 2 | 关联的标签 |

*(注：联合主键为 (post\_id, tag\_id)，创建双向索引以应对“查标签下所有帖子”或“查帖子的所有标签”的需求。)*



## Phase 2：核心 API 契约与接口规范 V1.2

### **1\. 全局规范与 RBAC 权限体系 (Global Standards & Roles)**

* **基础路径 (Base URL):** /api/v1  
* **鉴权方式:** HTTP Header 携带 Authorization: Bearer \<Token\>  
* **HTTP 状态码规范:** \* 200/201: 成功  
  * 400: 参数错误  
  * 401: 未登录或 Token 失效  
  * 403: 权限不足（如非 Admin 尝试调用管理接口）  
  * 409: 冲突（如学号已被绑定）  
  * 422: Pydantic 字段验证失败  
* **RBAC 角色枚举 (role 字段):**  
  * guest: 仅完成微信授权，未绑定学号，仅可浏览。  
  * student: 完成学籍绑定，可发帖、查看联系方式、修改个人昵称。  
  * admin: 预留的高权限“后门”账号。可发布广告（无视类型限制）、查看所有用户的真实姓名、封禁帖子。*(注：Admin 账号初期由数据库底层直接手动插入 openid 并修改 role='admin' 来提权)*。

## 

### **2\. 身份与鉴权模块 (Auth)**

#### **2.1 微信静默登录 (获取基础 Token)**

* **接口:** POST /api/v1/auth/login  
* **权限:** 公开  
* **逻辑:** 前端传入微信 code。后端调用微信接口换取 openid。若数据库中存在该 openid，则返回对应角色的 JWT；若不存在，则静默创建 role='guest' 的新用户。  
* **Request:**  
  JSON  
  { "code": "091xxxxxxxxx" }

* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "message": "success",  
    "data": {  
      "access\_token": "eyJhbGciOi...",  
      "role": "guest", // 或 "student", "admin"  
      "user\_info": {  
        "id": "uuid-xxxx",  
        "nickname": "鄂应学子\_48A2",  
        "is\_verified": false  
      }  
    }  
  }

#### **2.2 学籍认证绑定 (1:1 强绑定)**

* **接口:** POST /api/v1/auth/verify  
* **权限:** 需 guest Token  
* **逻辑:** 接收学号和密码，后端执行教务系统爬虫。抓取到 real\_name 后，**系统必须检查该 student\_id 是否已被其他账号绑定**。如果已被绑定，拒绝操作。验证成功后更新当前用户表，销毁密码变量，返回 student 权限的全新 JWT。  
* **Request:**  
  JSON  
  {  
    "student\_id": "2024xxxx",  
    "password": "your\_password"  
  }

* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "message": "认证成功",  
    "data": { "access\_token": "eyJhbGciOi...", "role": "student" }  
  }

* **Response (409 Conflict):**  
  JSON  
  {  
    "code": 40901,  
    "message": "该学号已被其他微信号绑定，请联系管理员申诉"  
  }

## 

### **3\. 用户资料模块 (User Profile) \- *新增***

#### **3.1 获取个人资料 (包含隐私信息)**

* **接口:** GET /api/v1/user/profile  
* **权限:** 需 student 或 admin Token  
* **逻辑:** 返回当前用户的详细信息，包含仅自己可见的 real\_name。  
* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "nickname": "代码敲不完",  
      "real\_name": "张三", // 隐私字段  
      "student\_id": "2024xxxx",  
      "wechat\_id": "wx\_zhangsan"  
    }  
  }

#### **3.2 更新用户资料**

* **接口:** PUT /api/v1/user/profile  
* **权限:** 需 student 或 admin Token  
* **逻辑:** 允许用户自定义 nickname（对外展示）和 wechat\_id（用于 C2C 联系）。real\_name 和 student\_id 锁定不可改。  
* **Request:**  
  JSON  
  {  
    "nickname": "全栈大怨种",  
    "wechat\_id": "new\_wx\_id"  
  }



### **4\. 文件上传模块 (Storage Adapter 模式)**

此模块采用动态策略下发机制。FastAPI 后端通过环境变量（如 STORAGE\_PROVIDER=cloudflare\_r2）来决定下发哪种上传配置。前端根据返回的 method 和 provider 执行具体的上传网络请求。

#### **4.1 获取上传配置与凭证**

* **接口:** GET /api/v1/upload/config  
* **权限:** 需 student 或 admin Token  
* **参数 (Query):**  
  * filename (如 test.jpg，用于后端预生成唯一路径)  
  * content\_type (如 image/jpeg)  
* **逻辑:** 后端生成对应存储平台的上传凭证，并提前分配好该文件在数据库中的最终访问链接 (public\_url)。

##### **场景 A：当前 MVP 阶段 (Cloudflare R2)**

后端使用 boto3 生成 S3 预签名 URL。前端收到后直接发起 PUT 请求。

* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "provider": "r2",  
      "method": "PUT",  
      "upload\_url": "https://\<account\_id\>.r2.cloudflarestorage.com/ey-wall/posts/2026/uuid.jpg?X-Amz-...",  
      "form\_data": null, // PUT 请求直接传二进制流，不需要表单字段  
      "public\_url": "https://img.yourdomain.com/posts/2026/uuid.jpg"  
    }  
  }

##### **场景 B：未来盈利后切换国内 OSS (以阿里云为例)**

后端生成 OSS PostObject 的 Policy 和 Signature。前端收到后发起 POST 表单请求。

* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "provider": "aliyun",  
      "method": "POST",  
      "upload\_url": "https://your-bucket.oss-cn-beijing.aliyuncs.com",  
      "form\_data": {  
        "key": "posts/2026/uuid.jpg",  
        "OSSAccessKeyId": "LTAI5t...",  
        "policy": "eyJleHB...",  
        "Signature": "QWErty..."  
      },  
      "public\_url": "https://img.yourdomain.com/posts/2026/uuid.jpg"  
    }  
  }

##### **场景 C：白嫖校内闲置服务器 (Local 本地存储)**

后端直接开放一个接收文件流的接口。前端向该接口发起 POST 请求（multipart/form-data）。

* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "provider": "local",  
      "method": "POST",  
      "upload\_url": "https://api.yourdomain.com/api/v1/upload/direct", // 指向你自己的后端直接上传接口  
      "form\_data": {  
        "path": "posts/2026/uuid.jpg"  
      },  
      "public\_url": "https://api.yourdomain.com/static/posts/2026/uuid.jpg"  
    }  
  }

### 

#### **4.2 前端 (Uni-app) 对应的统一伪代码逻辑参考**

通过这种设计，负责前端的同学只需要写一个 switch 语句，未来无论后端怎么切环境，前端都不需要发版：

JavaScript

// 1\. 请求上传配置  
const configRes \= await request('/api/v1/upload/config?filename=xxx.jpg');  
const { method, upload\_url, form\_data, public\_url } \= configRes.data;

// 2\. 根据下发的策略执行真实上传  
if (method \=== 'PUT') {  
    // 对应 R2 预签名直传  
    await uni.uploadFile({  
        url: upload\_url,  
        filePath: localImagePath,  
        name: 'file',  
        header: { 'Content-Type': 'image/jpeg' } // PUT 必须带 header  
    });  
} else if (method \=== 'POST') {  
    // 对应 阿里云/本地 策略  
    await uni.uploadFile({  
        url: upload\_url,  
        filePath: localImagePath,  
        name: 'file',  
        formData: form\_data // 动态带入后端下发的鉴权表单  
    });  
}

// 3\. 将 public\_url 加入到准备提交给后端的帖子 images 数组中



### **5\. 核心信息流模块 (Posts)**

#### **5.1 获取帖子列表 (游标分页 \+ 广告置顶)**

* **接口:** GET /api/v1/posts  
* **权限:** 公开  
* **逻辑:** WHERE id \< cursor。如果是 Admin 发布的 advertisement 类型的帖子，可以在 SQL 层面通过特定的权重字段进行置顶或随机插入信息流中。  
* **Response (200 OK):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "items": \[  
        {  
          "id": 1025,  
          "post\_type": "advertisement", // 管理员专属广告类型  
          "content": "\[周边商家\] 新开业剧本杀...",  
          "user": { "nickname": "官方运营喵" }, // 不暴露真实姓名  
          "images": \["https://img.yourdomain.com/ad.jpg"\],  
          "created\_at": "2026-05-10T22:00:00Z"  
        }  
      \],  
      "next\_cursor": 1025,  
      "has\_more": true  
    }  
  }

#### **5.2 发布帖子 (Admin 权限豁免)**

* **接口:** POST /api/v1/posts  
* **权限:** 需 student 或 admin Token  
* **逻辑:** Admin 发布时，允许传入 post\_type: "advertisement"，且直接跳过图片审核，状态直接标为 1 (正常)。Student 发布时走正常审核流。  
* **Request:**  
  JSON  
  {  
    "post\_type": "second\_hand", // Admin 可传 "advertisement"  
    "content": "出九成新算法导论...",  
    "images": \["https://img.yourdomain.com/...jpg"\],  
    "tag\_ids": \[1\]  
  }

#### **5.3 获取帖子详情 (隐私隔离核心)**

* **接口:** GET /api/v1/posts/{post\_id}  
* **权限:** 需基础 Token  
* **核心隐私逻辑 (FastAPI 层面的鉴权判断):**  
  1. 获取帖子的发帖人信息。  
  2. 判断当前请求者的 JWT：  
     * 如果是 **Admin**：返回中包含发帖人的 real\_name 和 contact\_wechat。  
     * 如果是 **发帖人本人**：返回中包含自己的 real\_name。  
     * 如果是 **普通 Student**：返回 contact\_wechat，但**隐藏** real\_name。  
     * 如果是 **Guest**：返回的 contact\_wechat 为 null，隐藏 real\_name。  
* **Response (200 OK \- Admin 视角的返回值):**  
  JSON  
  {  
    "code": 0,  
    "data": {  
      "id": 1024,  
      "content": "出九成新算法导论...",  
      "user": {  
        "nickname": "全栈大怨种",  
        "real\_name": "张三", // 仅 Admin 或本人可见  
        "student\_id": "2024001" // 仅 Admin 或本人可见  
      },  
      "contact\_wechat": "wx\_zhangsan" // Student 及以上可见  
    }  
  }



## Phase 3：关键业务流与逻辑时序

### 1\. 异步任务架构规范 (Async Task Processing)**

为了保证代码架构的可迁移性，MVP 阶段虽采用 FastAPI 自带的 BackgroundTasks，但必须严格遵守 **“调度与业务解耦”、“仅传递序列化参数”** 的设计原则。

#### **1.1 异步解耦设计规范 (代码示例)**

**严禁**在后台任务中传递 ORM 对象（如 Post 实例），**必须**传递基本数据类型（如 post\_id: int），由 Service 层去重新查询数据库。

```python
# 规范示例：未来迁移到 Celery 时，只需加一个 @celery.task 装饰器即可  
# \--- Service 层 (纯业务逻辑，完全解耦) \---  
async def process_image_security_check(post_id: int):  
    # 1\. 重新从数据库获取帖子 (兼容未来跨进程调用的上下文丢失问题)  
    post = await db.get_post_by_id(post_id)  
    if not post: return
    # 2\. 调用微信 API 检测图片 
    result = await wechat_api.check_media(post.images)
    # 3\. 结果处理  
	if result.is_risky:  
    	await db.update_post_status(post_id, status=-1)

# \--- Controller 层 (API 路由入口) \---  
@router.post("/posts")  
async def create_post(post_data: PostCreate, bg_tasks: BackgroundTasks):  
    # 1\. 同步入库，状态初始为 0 (待机审)  
    new_post_id = await db.create_post(post_data)  
	# 2\. 物理上使用 BackgroundTasks，逻辑上已为 Celery 留好坑位  
	bg_tasks.add_task(process_image_security_check, new_post_id)  
  
	return {"message": "发布成功，图片审核中", "post_id": new_post_id}
```



### **2\. 鉴权与反爬限流策略 (Auth & Rate Limiting)**

教务系统非常脆弱，且校园网出口 IP 集中，必须在 API 网关层做好强限流，防止爬虫脚本把教务系统打挂，连累小程序 IP 被封。

#### **2.1 针对 POST /api/v1/auth/verify 的限流配置**

* **限流维度：** 结合 IP 地址 与 openid 双重限流。  
* **限流阈值 (推荐值)：**  
  * **单 IP：** 最多 10 次 / 1 分钟。（考虑到宿舍共用路由器，阈值不能太低，但足以防范自动化爆破）。  
  * **单 OpenID：** 最多 5 次 / 10 分钟。（防止个别人疯狂重试密码）。  
* **触发拦截：** 达到阈值后，直接抛出 HTTP 429 Too Many Requests。  
* **实现方案：** MVP 阶段使用基于 Redis 的 Token Bucket（令牌桶）或简单的计数器 INCR \+ EXPIRE 实现。

#### **2.2 异常容错机制**

当爬虫请求教务系统发生超时（Timeout）或收到 HTTP 5xx 错误时，FastAPI 不得挂起，必须设置严格的超时时间（如 timeout=8s），超时后向前端返回友好提示：“学校教务系统正在开小差，请稍后再试”。



### **3\. C2C 交易风控与举报流 (Reporting Mechanism)**

为了防止恶意举报导致正常帖子被下架（恶意竞争），举报动作不干预帖子的真实状态，仅作为事件记录流入 Admin 后台。

#### **3.1 新增接口：提交举报**

* **接口:** POST /api/v1/posts/{post\_id}/report  
* **权限:** 需 student Token  
* **Request:**  
  JSON  
  {  
    "reason": "发布虚假微信号 / 违禁品 / 欺诈",  
    "description": "加了微信之后发现是推销信用卡的"  
  }

* **Response (200 OK):**  
  JSON  
  { "code": 0, "message": "举报成功，管理员将尽快核实" }

#### **3.2 举报流转逻辑 (State Machine)**

1. **记录生成：** 接收到举报请求后，后端在 reports 数据库表中插入一条记录，关联 post\_id、举报人 ID 和被举报人 ID，初始状态为 pending。  
2. **通知管理员：** \* 方案 A (低成本)：不写复杂的站内信，当有新举报时，直接通过企业微信机器人 Webhook 或钉钉机器人，发一条消息到你们团队的内部群：“⚠️ 有新举报：帖子 ID 1024，涉嫌欺诈”。  
   * 方案 B (常规)：Admin 用户登录小程序时，在“我的”页面显示一个红点角标。  
3. **人工介入 (Admin)：**  
   * Admin 通过 GET /api/v1/posts/{post\_id} (Admin 权限可看真实姓名和微信号) 核查信息。  
   * 确认违规后，Admin 调用接口将该帖子 status 变更为 \-1，并可选择冻结发帖人的账号 (users.status \= 0)。



### **4\. 全局状态机流转图 (Status Lifecycle)**

为了前端页面展示和后端 SQL 查询不产生歧义，定义 posts 表的 status 字段流转规则：

| 当前状态 | 触发动作                           | 新状态       | 业务意义                   | 前端展示                     |
| :------- | :--------------------------------- | :----------- | :------------------------- | :--------------------------- |
| None     | 用户点击发布，文本机审通过，落库   | 0 (待审核)   | 正在等待图片后台机审       | 仅本人可见列表显示“审核中”   |
| 0        | 异步微信接口回调：图片安全 (Pass)  | 1 (正常)     | 帖子合规，信息流可见       | 公开信息流展示               |
| 0        | 异步微信接口回调：图片违规 (Risky) | \-1 (屏蔽)   | 帖子违规，被系统拦截       | 仅本人可见，提示“含违规图片” |
| 1        | 用户(发帖人)点击“已解决/已出”      | 2 (已归档)   | 交易完成，不再占用公共资源 | 加盖“已出”印章，列表沉底     |
| 1 / 2    | 用户主动删除帖子                   | \-2 (软删除) | 用户自发删除（非物理删除） | 彻底消失                     |
| 1        | 被举报，Admin 后台点击确认违规     | \-1 (屏蔽)   | 被官方封禁                 | 彻底消失                     |

---



## Phase 4：自动化部署与 DevOps

### **1\. 密钥管理规范 (Secrets Management)**

绝对禁止将任何敏感信息提交到代码仓库。我们将采用 **“本地 .env 文件 \+ 线上 GitHub Secrets 动态注入”** 的策略。

#### **1.1 环境变量清单 (Environment Variables)**

在项目根目录维护一个 .env.example 提交到仓库，说明需要哪些配置：

Ini, TOML

\# .env.example  
DATABASE\_URL\=postgresql://user:password@db:5432/ey\_wall  
REDIS\_URL\=redis://redis:6379/0  
JWT\_SECRET\=your\_super\_secret\_key  
CF\_R2\_ACCOUNT\_ID\=xxx  
CF\_R2\_ACCESS\_KEY\=xxx  
CF\_R2\_SECRET\_KEY\=xxx

#### **1.2 GitHub Secrets 配置列表**

在 GitHub 仓库的 Settings \-\> Secrets and variables \-\> Actions 中，你需要提前配置以下机密信息，供流水线使用：

* **阿里云 ACR 凭证：**  
  * ALIYUN\_CR\_REGISTRY: registry.cn-beijing.aliyuncs.com (根据你的地域)  
  * ALIYUN\_CR\_USERNAME: 你的阿里云账号  
  * ALIYUN\_CR\_PASSWORD: ACR 独立密码  
* **VPS 服务器凭证：**  
  * VPS\_HOST: 服务器公网 IP  
  * VPS\_SSH\_KEY: 服务器的私钥 (PEM 格式)  
  * VPS\_USER: 通常为 root  
* **后端生产环境业务变量：** (如 DB\_PASSWORD, JWT\_SECRET 等)  
* **前端微信发布凭证：**  
  * WEAPP\_APPID: 小程序 AppID  
  * WEAPP\_UPLOAD\_KEY: 微信公众平台下载的私钥文件内容 (用于 miniprogram-ci)



### **2\. 后端自动化流水线 (Backend CI/CD)**

**战略路径：** GitHub Actions 构建 Docker 镜像 $\\rightarrow$ 推送至阿里云 ACR $\\rightarrow$ SSH 登录 VPS $\\rightarrow$ 动态生成 .env $\\rightarrow$ 拉取 ACR 镜像启动。

#### **2.1 生产环境 Docker Compose 编排 (docker-compose.yml)**

部署在 VPS 上的核心编排文件，数据库与 Redis 持久化，FastAPI 从 ACR 拉取镜像：

YAML

version: '3.8'  
services:  
  db:  
    image: postgres:15-alpine  
    restart: always  
    environment:  
      POSTGRES\_USER: ${DB\_USER}  
      POSTGRES\_PASSWORD: ${DB\_PASSWORD}  
      POSTGRES\_DB: ey\_wall  
    volumes:  
      \- pgdata:/var/lib/postgresql/data  
  redis:  
    image: redis:7-alpine  
    restart: always  
  api:  
    image: registry.cn-beijing.aliyuncs.com/your\_namespace/ey-wall-api:latest  
    restart: always  
    env\_file:  
      \- .env  
    ports:  
      \- "8000:8000"  
    depends\_on:  
      \- db  
      \- redis  
volumes:  
  pgdata:

#### **2.2 GitHub Actions 脚本蓝图 (.github/workflows/backend.yml)**

当 main 分支有代码推送时触发：

1. **Build & Push：**  
   * Check out 代码。  
   * 使用 ALIYUN\_CR\_\* 登录阿里云镜像库。  
   * 构建 FastAPI Docker 镜像并打上 latest 和 commit-sha 标签。  
   * 推送至阿里云 ACR。  
2. **Deploy to VPS：**  
   * 使用 appleboy/ssh-action 插件连接 VPS。  
   * 在 VPS 目标目录执行以下 Shell 命令 (伪代码逻辑)：  
     Bash  
     \# 1\. 登录阿里云 ACR (保证 VPS 能拉取私有镜像)  
     docker login \--username ${{ secrets.ALIYUN\_CR\_USERNAME }} ...  
     \# 2\. 将 GitHub Secrets 注入生成 VPS 上的 .env 文件  
     echo "DATABASE\_URL=${{ secrets.PROD\_DB\_URL }}" \> .env  
     echo "JWT\_SECRET=${{ secrets.JWT\_SECRET }}" \>\> .env  
     \# ... 写入其他变量  
     \# 3\. 拉取最新镜像并重启容器  
     docker-compose pull api  
     docker-compose up \-d \--remove-orphans



### **3\. 前端自动化流水线 (Frontend CI/CD)**

避免每次打包都在本地用开发者工具手动上传，借助官方工具包实现自动化。

#### **3.1 GitHub Actions 脚本蓝图 (.github/workflows/frontend.yml)**

当前端代码推送到 main 时触发：

1. **Environment Setup：**  
   * Check out 代码。  
   * 安装 Node.js 环境。  
2. **Build：**  
   * 执行 npm install。  
   * 执行 npm run build:mp-weixin (Uni-app 编译为微信小程序代码)。  
3. **Upload (miniprogram-ci)：**  
   * 将 GitHub Secrets 中的 WEAPP\_UPLOAD\_KEY 写入到一个临时文件 private.${APPID}.key。  
   * 执行上传脚本：  
     JavaScript  
     // 使用 miniprogram-ci 库  
     const ci \= require('miniprogram-ci');  
     const project \= new ci.Project({  
       appid: process.env.APPID,  
       type: 'miniProgram',  
       projectPath: 'dist/build/mp-weixin',  
       privateKeyPath: \`private.${process.env.APPID}.key\`,  
     });  
     ci.upload({  
       project,  
       version: '1.0.0', // 结合 Git Tag 动态生成  
       desc: 'GitHub Actions 自动构建',  
       setting: { es6: true, minify: true }  
     });



### **4\. “无域名”生存指南与后续规划 (Domain & ICP)**

在你决定好域名和完成备案之前，研发完全不会受阻。

#### **4.1 开发期的无域名解决方案**

1. **本地调试：** 在微信开发者工具右上角“详情” \-\> “本地设置”中，勾选 **“不校验合法域名、web-view（业务域名）、TLS版本以及HTTPS证书”**。此时前端可以直接请求本地运行的 FastAPI 接口（如 http://127.0.0.1:8000/api/v1）。  
2. **真机预览：** 确保手机和运行后端的电脑在同一个局域网（比如同一个 Wi-Fi 下）。将前端代码中的 API 基础路径改为你的**电脑局域网 IP**（如 http://192.168.x.x:8000/api/v1），即可在手机上扫码体验所有功能。

#### **4.2 域名与备案破局路线图 (并行任务)**

MVP 跑通并准备上线前的必做事项：

1. **选购域名：** 推荐阿里云或腾讯云购买普通的 .com 或 .cn。不建议购买太生僻的后缀，某些后缀在中国大陆无法进行 ICP 备案。  
2. **ICP 备案（需 1-3 周）：** 购买国内服务器后，通过云厂商的备案系统提交个人身份证信息即可。审核期间不需要网站能够访问。  
3. **配置 HTTPS：** 备案通过后，将域名解析到 VPS。在 VPS 上安装 Nginx，利用 Certbot 申请免费的 Let's Encrypt 证书。  
4. **填入微信白名单：** 登录微信公众平台，将 https://api.yourdomain.com 填入 request合法域名，将 https://img.yourdomain.com 填入 uploadFile合法域名 和 downloadFile合法域名。



## **结案陈词**

从 **架构底座设计 (Phase 1\)** $\\rightarrow$ **API 契约制定 (Phase 2\)** $\\rightarrow$ **核心业务逻辑与容错流转 (Phase 3\)** $\\rightarrow$ **全链路自动化 DevOps (Phase 4\)**。

至此，鄂应墙小程序 MVP 的全套工程技术图纸已经**全部交付**。这套方案完美平衡了单兵作战能力、资金成本以及高并发下的系统健壮性。