# 域名与部署前检查

当前发布包没有猜测尚未购买的域名。域名确认后，部署前完成以下事项：

1. 将真实姓名写入首页标题、Person JSON-LD 的 `name` 字段和站点介绍；`NineSense` 继续作为 `alternateName`。
2. 在首页 `<head>` 添加正式域名的 `canonical`，并添加 `og:url`。
3. 将 `og:image` 和 `twitter:image` 改为分享图的 HTTPS 绝对地址。
4. 新建 `sitemap.xml`，首页地址必须使用正式域名的绝对地址。
5. 在 `robots.txt` 末尾加入 `Sitemap: https://正式域名/sitemap.xml`。
6. 备案完成后，在页脚显示 ICP备案号，并链接到 `https://beian.miit.gov.cn/`。
7. 配置 HTTPS，确认 HTTP 自动跳转到 HTTPS；证书稳定后再启用 HSTS。
8. 服务器为图片、CSS 和脚本开启 Brotli 或 gzip，并设置长期缓存；HTML 使用短缓存或协商缓存。
9. 配置 `X-Content-Type-Options: nosniff`、`Referrer-Policy: strict-origin-when-cross-origin` 和合适的 Content-Security-Policy。
10. 部署后重新检查 404 状态码、分享预览、搜索引擎抓取和三种屏幕宽度。
