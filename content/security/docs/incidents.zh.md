# 事件响应和取证

您快速应对事件的能力可以帮助最小化违规造成的损害。拥有可靠的警报系统来警告您可疑行为是良好事件响应计划的第一步。当发生事件时，您必须快速决定是销毁并替换受影响的容器，还是隔离并检查容器。如果您选择隔离容器作为取证调查和根本原因分析的一部分，那么应该遵循以下一系列活动:

## 示例事件响应计划

### 识别违规的 Pod 和工作节点

您的首要行动应该是隔离损害。首先确定违规发生在哪里，并将该 Pod 及其节点与其余基础架构隔离。

### 使用工作负载名称识别违规的 Pod 和工作节点

如果您知道违规 pod 的名称和命名空间，您可以按如下方式识别运行该 pod 的工作节点:

```bash
kubectl get pods <name> --namespace <namespace> -o=jsonpath='{.spec.nodeName}{"\n"}'   
```

如果 [工作负载资源](https://kubernetes.io/docs/concepts/workloads/controllers/) 如 Deployment 遭到破坏，则很可能该工作负载资源的所有 pod 都遭到破坏。使用以下命令列出工作负载资源的所有 pod 及其运行所在的节点:

```bash
selector=$(kubectl get deployments <name> \
 --namespace <namespace> -o json | jq -j \
'.spec.selector.matchLabels | to_entries | .[] | "\(.key)=\(.value)"')

kubectl get pods --namespace <namespace> --selector=$selector \
-o json | jq -r '.items[] | "\(.metadata.name) \(.spec.nodeName)"'
```

上述命令适用于 deployment。您可以为其他工作负载资源(如 replicasets、statefulsets 等)运行相同的命令。

### 使用服务帐户名称识别违规的 Pod 和工作节点

在某些情况下，您可能会发现服务账户已被入侵。使用已识别的服务账户的 Pod 很可能已被入侵。您可以使用以下命令识别使用该服务账户的所有 Pod 及其运行所在的节点:

```bash
kubectl get pods -o json --namespace <namespace> | \
    jq -r '.items[] |
    select(.spec.serviceAccount == "<service account name>") |
    "\(.metadata.name) \(.spec.nodeName)"'
```

### 识别使用了存在漏洞或已被入侵的镜像的 Pod 和工作节点

在某些情况下，您可能会发现在集群上运行的 Pod 中使用的容器镜像是恶意或已被入侵的。如果发现容器镜像包含恶意软件、是已知的恶意镜像或存在已被利用的 CVE 漏洞，则该容器镜像被视为恶意或已被入侵。您应该将使用该容器镜像的所有 Pod 视为已被入侵。您可以使用以下命令识别使用该镜像的 Pod 及其运行所在的节点:

```bash
IMAGE=<恶意/已被入侵镜像的名称>

kubectl get pods -o json --all-namespaces | \
    jq -r --arg image "$IMAGE" '.items[] | 
    select(.spec.containers[] | .image == $image) | 
    "\(.metadata.name) \(.metadata.namespace) \(.spec.nodeName)"'
```

### 通过创建拒绝所有入站和出站流量的网络策略来隔离 Pod

拒绝所有流量的规则可以帮助阻止正在进行的攻击，方法是切断与 Pod 的所有连接。以下网络策略将应用于带有标签 `app=web` 的 Pod。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector:
    matchLabels: 
      app: web
  policyTypes:
  - Ingress
  - Egress
```

!!! attention
    如果攻击者已经获得了底层主机的访问权限，网络策略可能会失效。如果您怀疑发生了这种情况，您可以使用[AWS 安全组](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html)将受损主机与其他主机隔离。更改主机的安全组时，请注意它将影响在该主机上运行的所有容器。

### 如有必要，撤销分配给 Pod 或工作节点的临时安全凭证

如果工作节点被分配了允许 Pod 访问其他 AWS 资源的 IAM 角色，请从实例中删除这些角色，以防止攻击造成进一步损害。同样，如果 Pod 被分配了 IAM 角色，请评估是否可以安全地从该角色中删除 IAM 策略，而不会影响其他工作负载。

### 封锁工作节点

通过封锁受影响的工作节点，您会通知调度程序避免将 Pod 调度到受影响的节点。这将允许您移除节点以进行取证研究，而不会中断其他工作负载。

!!! info
    此指南不适用于 Fargate，因为每个 Fargate Pod 都在自己的沙箱环境中运行。相反，通过应用拒绝所有入站和出站流量的网络策略来隔离受影响的 Fargate Pod。

### 对受影响的工作节点启用终止保护

攻击者可能会尝试通过终止受影响的节点来抹去他们的罪行。启用[终止保护](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html#Using_ChangingDisableAPITermination)可以防止这种情况发生。[实例缩减保护](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-instance-termination.html#instance-protection)将保护节点免受缩减事件的影响。

!!! warning
    您无法对 Spot 实例启用终止保护。

### 使用标签标记有问题的 Pod/节点，表明它是正在进行的调查的一部分

这将作为一个警告，提醒集群管理员在调查完成之前不要篡改受影响的 Pod/节点。

### 在工作节点上捕获易失性工件

- **捕获操作系统内存**。这将捕获 Docker 守护进程(或其他容器运行时)及其每个容器的子进程。可以使用诸如 [LiME](https://github.com/504ensicsLabs/LiME) 和 [Volatility](https://www.volatilityfoundation.org/) 之类的工具来实现，或者通过构建在它们之上的更高级别的工具，如 [Amazon EC2 自动化取证编排器](https://aws.amazon.com/solutions/implementations/automated-forensics-orchestrator-for-amazon-ec2/)。
- **执行正在运行的进程和打开端口的 netstat 树转储**。这将捕获 docker 守护进程及其每个容器的子进程。
- **在证据被篡改之前运行命令保存容器级别的状态**。您可以使用容器运行时的功能来捕获有关当前正在运行的容器的信息。例如，使用 Docker，您可以执行以下操作:
  - `docker top CONTAINER` 查看正在运行的进程。
  - `docker logs CONTAINER` 查看守护进程级别的日志。
  - `docker inspect CONTAINER` 查看有关容器的各种信息。

    使用 [nerdctl](https://github.com/containerd/nerdctl) CLI 可以在 containerd 中实现相同的功能，代替 `docker`(例如 `nerdctl inspect`)。根据容器运行时，可能还有一些其他命令可用。例如，Docker 有 `docker diff` 来查看容器文件系统的更改，或 `docker checkpoint` 来保存所有容器状态，包括易失性内存(RAM)。有关 containerd 或 CRI-O 运行时的类似功能的讨论，请参阅[此 Kubernetes 博客文章](https://kubernetes.io/blog/2022/12/05/forensic-container-checkpointing-alpha/)。

- **暂停容器以进行取证捕获**。
- **快照实例的 EBS 卷**。

### 重新部署受损的 Pod 或工作负载资源

一旦您已经收集了用于取证分析的数据，您就可以重新部署受损的 pod 或工作负载资源。

首先推出修复被入侵漏洞的补丁并启动新的替换 pod。然后删除存在漏洞的 pod。

如果存在漏洞的 pod 由更高级别的 Kubernetes 工作负载资源管理(例如 Deployment 或 DaemonSet),删除它们将会调度新的 pod。因此存在漏洞的 pod 将再次启动。在这种情况下，您应该在修复漏洞后部署新的替换工作负载资源。然后您应该删除存在漏洞的工作负载。

## 建议

### 查阅 AWS 安全事件响应白皮书

虽然本节简要概述了处理可疑安全漏洞的一些建议，但该主题在白皮书 [AWS 安全事件响应](https://docs.aws.amazon.com/whitepapers/latest/aws-security-incident-response-guide/welcome.html)中有详尽的介绍。

### 实践安全游戏日

将您的安全从业人员分为红队和蓝队两个团队。红队将专注于探测不同系统的漏洞，而蓝队将负责防御。如果您没有足够的安全从业人员组建独立的团队，可以考虑雇佣了解 Kubernetes 漏洞的外部实体。

[Kubesploit](https://github.com/cyberark/kubesploit) 是 CyberArk 提供的一个渗透测试框架，您可以使用它来进行游戏日活动。与其他扫描集群漏洞的工具不同，kubesploit 模拟真实世界的攻击。这让您的蓝队有机会练习对攻击的响应，并评估其有效性。

### 对集群运行渗透测试

定期攻击您自己的集群可以帮助您发现漏洞和错误配置。在开始之前，请先遵循[渗透测试指南](https://aws.amazon.com/security/penetration-testing/)对集群进行测试。

## 工具和资源

- [kube-hunter](https://github.com/aquasecurity/kube-hunter)，一款针对 Kubernetes 的渗透测试工具。
- [Gremlin](https://www.gremlin.com/product/#kubernetes)，一款混沌工程工具包，可用于模拟针对应用程序和基础设施的攻击。
- [攻击和防御 Kubernetes 安装](https://github.com/kubernetes/sig-security/blob/main/sig-security-external-audit/security-audit-2019/findings/AtredisPartners_Attacking_Kubernetes-v1.0.pdf)
- [kubesploit](https://www.cyberark.com/resources/threat-research-blog/kubesploit-a-new-offensive-tool-for-testing-containerized-environments)
- [SUSE 的 NeuVector](https://www.suse.com/neuvector/) 开源零信任容器安全平台，提供漏洞和风险报告以及安全事件通知
- [高级持续威胁](https://www.youtube.com/watch?v=CH7S5rE3j8w)
- [Kubernetes 实战攻防](https://www.youtube.com/watch?v=LtCx3zZpOfs)
- [通过利用 RBAC 权限来入侵 Kubernetes 集群](https://www.youtube.com/watch?v=1LMo0CftVC4)