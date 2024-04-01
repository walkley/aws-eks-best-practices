# 为 Windows Pod 和容器配置 gMSA

## 什么是 gMSA 账户

基于 Windows 的应用程序(如 .NET 应用程序)通常使用 Active Directory 作为身份提供程序，使用 NTLM 或 Kerberos 协议进行授权/身份验证。

应用程序服务器需要与 Active Directory 交换 Kerberos 票证，因此需要加入域。Windows 容器不支持加入域，并且对于临时资源的容器来说也没有太大意义，因为这会给 Active Directory RID 池带来负担。

但是，管理员可以利用 [gMSA Active Directory](https://docs.microsoft.com/en-us/windows-server/security/group-managed-service-accounts/group-managed-service-accounts-overview) 账户为资源(如 Windows 容器、NLB 和服务器群集)协商 Windows 身份验证。

## Windows 容器和 gMSA 使用案例

利用 Windows 身份验证并以 Windows 容器形式运行的应用程序可从 gMSA 中获益，因为 Windows 节点将代表容器交换 Kerberos 票证。有两种选择可以设置 Windows 工作节点以支持 gMSA 集成:

#### 1 - 加入域的 Windows 工作节点
在此设置中，Windows 工作节点加入了 Active Directory 域，并且 Windows 工作节点的 AD 计算机账户用于对 Active Directory 进行身份验证并检索将与 Pod 一起使用的 gMSA 身份。

在加入域的方法中，您可以使用现有的 Active Directory GPO 轻松管理和加固您的 Windows 工作节点;但是，它会在 Windows 工作节点加入 Kubernetes 集群时产生额外的操作开销和延迟，因为它需要在节点启动期间进行额外的重新启动，并在 Kubernetes 集群终止节点后进行 Active Directory 垃圾清理。

在以下博客文章中，您将找到有关如何实现加入域的 Windows 工作节点方法的详细分步说明:

#### 2 - 无域Windows工作节点
在此设置中，Windows工作节点未加入Active Directory域，并使用"可移植"身份(用户/密码)对Active Directory进行身份验证，并检索要与pod一起使用的gMSA身份。

![](./images/domainless_gmsa.png)

可移植身份是Active Directory用户;该身份(用户/密码)存储在AWS Secrets Manager或AWS Systems Manager Parameter Store中，AWS开发的名为ccg_plugin的插件将用于从AWS Secrets Manager或AWS Systems Manager Parameter Store中检索此身份，并将其传递给containerd以检索gMSA身份并使其可用于pod。

在这种无域方法中，您可以在使用gMSA时避免Windows工作节点启动期间与Active Directory进行任何交互，并减少Active Directory管理员的操作开销。

在以下博客文章中，您将找到有关如何实现无域Windows工作节点方法的详细分步说明:

[Amazon EKS Windows pods的无域Windows身份验证](https://aws.amazon.com/blogs/containers/domainless-windows-authentication-for-amazon-eks-windows-pods/)

#### 重要注意事项

尽管pod能够使用gMSA帐户，但仍需要相应地设置应用程序或服务以支持Windows身份验证，例如，为了设置Microsoft IIS以支持Windows身份验证，您应通过dockerfile进行准备:

```dockerfile
RUN Install-WindowsFeature -Name Web-Windows-Auth -IncludeAllSubFeature
RUN Import-Module WebAdministration; Set-ItemProperty 'IIS:\AppPools\SiteName' -name processModel.identityType -value 2
RUN Import-Module WebAdministration; Set-WebConfigurationProperty -Filter '/system.webServer/security/authentication/anonymousAuthentication' -Name Enabled -Value False -PSPath 'IIS:\' -Location 'SiteName'
RUN Import-Module WebAdministration; Set-WebConfigurationProperty -Filter '/system.webServer/security/authentication/windowsAuthentication' -Name Enabled -Value True -PSPath 'IIS:\' -Location 'SiteName'
```