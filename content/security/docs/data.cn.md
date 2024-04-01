# 数据加密和密钥管理

## 静态加密

您可以在 Kubernetes 中使用三种不同的 AWS 原生存储选项：[EBS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEBS.html)、[EFS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AmazonEFS.html) 和 [FSx for Lustre](https://docs.aws.amazon.com/fsx/latest/LustreGuide/what-is.html)。这三种选项都提供使用服务管理密钥或客户主密钥 (CMK) 的静态加密。对于 EBS，您可以使用内置存储驱动程序或 [EBS CSI 驱动程序](https://github.com/kubernetes-sigs/aws-ebs-csi-driver)。两者都包含用于加密卷和提供 CMK 的参数。对于 EFS，您可以使用 [EFS CSI 驱动程序](https://github.com/kubernetes-sigs/aws-efs-csi-driver)，但与 EBS 不同，EFS CSI 驱动程序不支持动态配置。如果您想在 EKS 中使用 EFS，您需要在创建 PV 之前为文件系统预配置和配置静态加密。有关 EFS 文件加密的更多信息，请参阅 [加密静态数据](https://docs.aws.amazon.com/efs/latest/ug/encryption-at-rest.html)。除了提供静态加密外，EFS 和 FSx for Lustre 还包括加密传输数据的选项。FSx for Luster 默认执行此操作。对于 EFS，您可以通过在 PV 中的 `mountOptions` 中添加 `tls` 参数来添加传输加密，如下例所示：

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv
spec:
  capacity:
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: efs-sc
  mountOptions:
    - tls
  csi:
    driver: efs.csi.aws.com
    volumeHandle: <file_system_id>
```

[FSx CSI 驱动程序](https://github.com/kubernetes-sigs/aws-fsx-csi-driver)支持动态配置 Lustre 文件系统。它默认使用服务管理密钥加密数据，但也可以选择提供自己的 CMK，如下例所示：

```yaml
种类: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: fsx-sc
provisioner: fsx.csi.aws.com
parameters:
  subnetId: subnet-056da83524edbe641
  securityGroupIds: sg-086f61ea73388fb6b
  deploymentType: PERSISTENT_1
  kmsKeyId: <kms_arn>
```

!!! 注意
    从2020年5月28日起，写入EKS Fargate pods中临时卷的所有数据都将默认使用行业标准的AES-256加密算法进行加密。您无需对应用程序进行任何修改，因为加密和解密都由服务无缝处理。

### 对静态数据进行加密

加密静态数据被认为是最佳实践。如果您不确定是否需要加密，请对数据进行加密。

### 定期轮换您的CMK

配置KMS以自动轮换您的CMK。这将每年轮换一次您的密钥，同时无限期保存旧密钥，以便您的数据仍然可以被解密。有关更多信息，请参阅[轮换客户主密钥](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)

### 使用EFS访问点来简化对共享数据集的访问

如果您有具有不同POSIX文件权限的共享数据集或希望通过创建不同的挂载点来限制对共享文件系统的部分访问，请考虑使用EFS访问点。要了解有关使用访问点的更多信息，请参阅[https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html)。如今，如果您想使用访问点(AP),您需要在PV的`volumeHandle`参数中引用该AP。

!!! attention
    从2021年3月23日起，EFS CSI驱动程序支持动态配置EFS访问点。访问点是进入EFS文件系统的特定于应用程序的入口点，可以更轻松地在多个pod之间共享文件系统。每个EFS文件系统最多可以有120个PV。有关更多信息，请参阅[介绍Amazon EFS CSI动态配置](https://aws.amazon.com/blogs/containers/introducing-efs-csi-dynamic-provisioning/)。

## 密钥管理

Kubernetes密钥用于存储敏感信息，如用户证书、密码或API密钥。它们作为base64编码的字符串持久存储在etcd中。在EKS上，etcd节点的EBS卷使用[EBS加密](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSEncryption.html)进行加密。Pod可以通过在`podSpec`中引用密钥来检索Kubernetes密钥对象。这些密钥可以映射到环境变量或作为卷挂载。有关创建密钥的更多信息，请参阅[https://kubernetes.io/docs/concepts/configuration/secret/](https://kubernetes.io/docs/concepts/configuration/secret/)。

!!! caution
    特定命名空间中的密钥可以被该密钥所在命名空间中的所有pod引用。

!!! caution
    节点授权器允许Kubelet读取挂载到节点的所有密钥。

### 使用AWS KMS进行Kubernetes密钥的信封加密

这允许您使用唯一的数据加密密钥(DEK)加密您的密钥。然后，DEK使用来自AWS KMS的密钥加密密钥(KEK)进行加密，KEK可以自动按照重复的时间表轮换。使用Kubernetes的KMS插件，所有Kubernetes密钥都以密文而不是纯文本的形式存储在etcd中，并且只能由Kubernetes API服务器解密。
有关更多详细信息，请参阅[使用EKS加密提供程序支持进行深度防御](https://aws.amazon.com/blogs/containers/using-eks-encryption-provider-support-for-defense-in-depth/)

### 审计Kubernetes密钥的使用

在 EKS 上，启用审计日志记录并创建 CloudWatch 指标过滤器和告警，以在使用机密时提醒您(可选)。以下是 Kubernetes 审计日志的指标过滤器示例，`{($.verb="get") && ($.objectRef.resource="secret")}`。您还可以使用以下查询与 CloudWatch Log Insights:

```bash
fields @timestamp, @message
| sort @timestamp desc
| limit 100
| stats count(*) by objectRef.name as secret
| filter verb="get" and objectRef.resource="secrets"
```

上述查询将显示在特定时间范围内访问机密的次数。

```bash
fields @timestamp, @message
| sort @timestamp desc
| limit 100
| filter verb="get" and objectRef.resource="secrets"
| display objectRef.namespace, objectRef.name, user.username, responseStatus.code
```

此查询将显示机密以及尝试访问机密的用户的命名空间、用户名和响应代码。

### 定期轮换您的机密

Kubernetes 不会自动轮换机密。如果您必须轮换机密，请考虑使用外部机密存储，例如 Vault 或 AWS Secrets Manager。

### 使用单独的命名空间作为隔离不同应用程序机密的方式

如果您有不能在命名空间中共享的机密，请为这些应用程序创建单独的命名空间。

### 使用卷挂载而不是环境变量

环境变量的值可能会无意中出现在日志中。作为卷挂载的机密被实例化为 tmpfs 卷(基于 RAM 的文件系统),当 pod 被删除时会自动从节点中删除。

### 使用外部机密提供程序

使用Kubernetes secrets有几种可行的替代方案，包括[AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)和Hashicorp的[Vault](https://www.hashicorp.com/blog/injecting-vault-secrets-into-kubernetes-pods-via-a-sidecar/)。这些服务提供了Kubernetes Secrets所没有的功能，如细粒度访问控制、强加密和自动轮换secrets。Bitnami的[Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)是另一种方法，它使用非对称加密来创建"sealed secrets"。公钥用于加密secret，而私钥用于解密secret，并保存在集群内部，允许您安全地将sealed secrets存储在Git等源代码控制系统中。有关更多信息，请参阅[使用Sealed Secrets在Kubernetes中管理secrets部署](https://aws.amazon.com/blogs/opensource/managing-secrets-deployment-in-kubernetes-using-sealed-secrets/)。

随着对外部secrets存储的使用不断增加，与Kubernetes集成的需求也随之增加。[Secret Store CSI Driver](https://github.com/kubernetes-sigs/secrets-store-csi-driver)是一个社区项目，它使用CSI驱动程序模型从外部secret存储中获取secrets。目前，该驱动程序支持[AWS Secrets Manager](https://github.com/aws/secrets-store-csi-driver-provider-aws)、Azure、Vault和GCP。AWS提供程序同时支持AWS Secrets Manager**和**AWS Parameter Store。它还可以配置为在secrets过期时轮换secrets，并可以将AWS Secrets Manager secrets同步到Kubernetes Secrets。当您需要将secret作为环境变量引用而不是从卷中读取它们时，同步secrets会很有用。

!!! note
    当秘密存储CSI驱动程序需要获取秘密时，它会假定引用该秘密的pod分配的IRSA角色。此操作的代码可在[此处](https://github.com/aws/secrets-store-csi-driver-provider-aws/blob/main/auth/auth.go)找到。

有关AWS Secrets & Configuration Provider (ASCP)的更多信息，请参阅以下资源:

- [如何使用AWS Secrets Configuration Provider与Kubernetes Secret Store CSI驱动程序](https://aws.amazon.com/blogs/security/how-to-use-aws-secrets-configuration-provider-with-kubernetes-secrets-store-csi-driver/)
- [将Secrets Manager秘密与Kubernetes Secrets Store CSI驱动程序集成](https://docs.aws.amazon.com/secretsmanager/latest/userguide/integrating_csi_driver.html)

[external-secrets](https://github.com/external-secrets/external-secrets)是另一种在Kubernetes中使用外部秘密存储的方式。与CSI驱动程序一样，external-secrets可以与各种不同的后端一起使用，包括AWS Secrets Manager。不同之处在于，external-secrets不是从外部秘密存储中检索秘密，而是将这些后端的秘密复制到Kubernetes作为Secrets。这使您可以使用首选的秘密存储来管理秘密，并以Kubernetes原生的方式与秘密进行交互。

## 工具和资源

- [Amazon EKS安全沉浸式研讨会 - 数据加密和秘密管理](https://catalog.workshops.aws/eks-security-immersionday/en-US/13-data-encryption-and-secret-management)