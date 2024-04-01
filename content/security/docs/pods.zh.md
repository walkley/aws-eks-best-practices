# Pod 安全性

Pod 规范包括各种不同的属性，可以加强或削弱您的整体安全态势。作为 Kubernetes 从业者，您的主要关注点应该是防止在容器中运行的进程逃离容器运行时的隔离边界并获得对底层主机的访问权限。

## Linux 权能

在容器中运行的进程默认在 \[Linux\] 根用户的上下文中运行。尽管根在容器内的操作部分受到容器运行时为容器分配的 Linux 权能集的约束，但这些默认权限可能允许攻击者升级他们的权限和/或访问绑定到主机的敏感信息，包括 Secret 和 ConfigMap。以下是分配给容器的默认权能列表。有关每个权能的更多信息，请参阅 [http://man7.org/linux/man-pages/man7/capabilities.7.html](http://man7.org/linux/man-pages/man7/capabilities.7.html)。

`CAP_AUDIT_WRITE, CAP_CHOWN, CAP_DAC_OVERRIDE, CAP_FOWNER, CAP_FSETID, CAP_KILL, CAP_MKNOD, CAP_NET_BIND_SERVICE, CAP_NET_RAW, CAP_SETGID, CAP_SETUID, CAP_SETFCAP, CAP_SETPCAP, CAP_SYS_CHROOT`

!!! 信息

  EC2 和 Fargate pod 默认被分配上述权能。此外，只能从 Fargate pod 中删除 Linux 权能。

以特权模式运行的 Pod 继承了主机上与 root 相关的所有 Linux 权能。如果可能的话，应该避免这种情况。

### 节点授权

所有 Kubernetes 工作节点都使用一种称为 [节点授权](https://kubernetes.io/docs/reference/access-authn-authz/node/) 的授权模式。节点授权允许来自 kubelet 的所有 API 请求，并允许节点执行以下操作:

读取操作:

- 服务
- 端点
- 节点
- Pod
- 与绑定到 kubelet 节点的 Pod 相关的 Secret、ConfigMap、持久卷声明和持久卷

写操作:

- 节点和节点状态(启用`NodeRestriction`准入插件以限制kubelet仅修改自身节点)
- pods和pod状态(启用`NodeRestriction`准入插件以限制kubelet仅修改绑定到自身的pods)
- 事件

与身份验证相关的操作:

- 对CertificateSigningRequest (CSR) API的读/写访问权限，用于TLS引导
- 创建TokenReview和SubjectAccessReview的能力，用于委派身份验证/授权检查

EKS使用[节点限制准入控制器](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#noderestriction),它只允许节点修改有限的节点属性和绑定到该节点的pod对象。然而，即使攻击者设法访问了主机，他们仍然可以从Kubernetes API中获取有关环境的敏感信息，从而在集群内进行横向移动。

## Pod安全解决方案

### Pod安全策略(PSP)

过去，[Pod安全策略(PSP)](https://kubernetes.io/docs/concepts/policy/pod-security-policy/)资源用于指定pods在创建之前必须满足的一组要求。从Kubernetes 1.21版本开始，PSP已被弃用。它们计划在Kubernetes 1.25版本中被移除。

!!! 注意

  [PSP在Kubernetes 1.21版本中已被弃用](https://kubernetes.io/blog/2021/04/06/podsecuritypolicy-deprecation-past-present-and-future/)。您将有大约2年的时间过渡到替代方案。这个[文档](https://github.com/kubernetes/enhancements/blob/master/keps/sig-auth/2579-psp-replacement/README.md#motivation)解释了弃用PSP的动机。

### 迁移到新的pod安全解决方案

由于PSP已在Kubernetes v1.25中被移除，集群管理员和操作员必须替换这些安全控制。两种解决方案可以满足这一需求:

- 来自Kubernetes生态系统的策略即代码 (PAC) 解决方案
- Kubernetes [Pod 安全标准 (PSS)](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

PAC 和 PSS 解决方案都可以与 PSP 共存;在移除 PSP 之前，它们可以在集群中使用。这有助于在从 PSP 迁移时采用。在考虑从 PSP 迁移到 PSS 时，请参阅此[文档](https://kubernetes.io/docs/tasks/configure-pod-container/migrate-from-psp/)。

Kyverno 是下面概述的 PAC 解决方案之一，在从 PSP 迁移到其解决方案时，包括类似的策略、功能比较和迁移程序，在一篇[博客文章](https://kyverno.io/blog/2023/05/24/podsecuritypolicy-migration-with-kyverno/)中有具体的指导。关于使用 Kyverno 迁移到 Pod 安全准入 (PSA) 的其他信息和指导已在 AWS 博客[这里](https://aws.amazon.com/blogs/containers/managing-pod-security-on-amazon-eks-with-kyverno/)发布。

### 策略即代码 (PAC)

策略即代码 (PAC) 解决方案通过规定和自动化控制提供防护栏，引导集群用户并防止不希望的行为。PAC 使用 [Kubernetes 动态准入控制器](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)通过 Webhook 调用拦截 Kubernetes API 服务器请求流程，并根据以代码形式编写和存储的策略变更和验证请求负载。变更和验证发生在 API 服务器请求导致集群发生变化之前。PAC 解决方案使用策略根据分类和值来匹配和处理 API 服务器请求负载。

Kubernetes 有几种开源 PAC 解决方案可用。这些解决方案不是 Kubernetes 项目的一部分;它们来自 Kubernetes 生态系统。下面列出了一些 PAC 解决方案。

- [OPA/Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [Open Policy Agent (OPA)](https://www.openpolicyagent.org/)
- [Kyverno](https://kyverno.io/)
- [Kubewarden](https://www.kubewarden.io/)
- [jsPolicy](https://www.jspolicy.com/)

有关 PAC 解决方案的更多信息以及如何帮助您选择适合您需求的合适解决方案，请参阅下面的链接。

- [基于策略的 Kubernetes 对策 - 第 1 部分](https://aws.amazon.com/blogs/containers/policy-based-countermeasures-for-kubernetes-part-1/)
- [基于策略的 Kubernetes 对策 - 第 2 部分](https://aws.amazon.com/blogs/containers/policy-based-countermeasures-for-kubernetes-part-2/)

### Pod 安全标准 (PSS) 和 Pod 安全准入 (PSA)

为了响应 PSP 弃用以及对开箱即用的 Kubernetes 内置解决方案控制 pod 安全性的持续需求，Kubernetes [Auth 特别兴趣小组](https://github.com/kubernetes/community/tree/master/sig-auth)创建了 [Pod 安全标准 (PSS)](https://kubernetes.io/docs/concepts/security/pod-security-standards/) 和 [Pod 安全准入 (PSA)](https://kubernetes.io/docs/concepts/security/pod-security-admission/)。PSA 工作包括一个 [准入控制器 Webhook 项目](https://github.com/kubernetes/pod-security-admission#pod-security-admission)，该项目实现了 PSS 中定义的控制措施。这种准入控制器方法类似于 PAC 解决方案中使用的方法。

根据 Kubernetes 文档，PSS _"定义了三种不同的策略来广泛涵盖安全范围。这些策略是累积的，从高度宽松到高度限制。"_

这些策略定义如下:

- **特权：** 不受限制(不安全)的策略，提供最广泛的权限级别。该策略允许已知的权限提升。这是没有策略的情况。对于需要特权访问的应用程序(如日志代理、CNI、存储驱动程序和其他系统范围的应用程序)来说，这很好。

- **基线：** 最小限制性策略，可防止已知的权限提升。允许默认(最小指定)的 Pod 配置。基线策略禁止使用 hostNetwork、hostPID、hostIPC、hostPath、hostPort,无法添加 Linux 功能，以及其他一些限制。

- **受限：** 严格限制的策略，遵循当前的 Pod 加固最佳实践。该策略继承自基线并添加了进一步的限制，例如无法以 root 或 root 组身份运行。受限策略可能会影响应用程序的功能。它们主要针对运行安全关键应用程序。

这些策略定义了[Pod 执行配置文件](https://kubernetes.io/docs/concepts/security/pod-security-standards/#profile-details),分为三个特权与受限访问级别。

为了实施 PSS 定义的控制措施，PSA 有三种模式:

- **enforce:** 违反策略将导致 Pod 被拒绝。

- **audit:** 违反策略将触发在审计日志中记录的事件添加审计注释，但其他情况下允许。

- **warn:** 违反策略将触发面向用户的警告，但其他情况下允许。

这些模式和配置文件(限制)级别是在 Kubernetes 命名空间级别使用标签配置的，如下例所示。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: policy-test
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

当单独使用时，这些操作模式会产生不同的响应，从而导致不同的用户体验。_enforce_ 模式将阻止创建违反配置的限制级别的相应 podSpecs 的 pod。但是在此模式下，创建 pod 的非 pod Kubernetes 对象(如 Deployment)将不会被阻止应用到集群，即使其中的 podSpec 违反了应用的 PSS。在这种情况下，Deployment 将被应用，而 pod 将被阻止应用。

这是一种令人困惑的用户体验，因为成功应用的 Deployment 对象并没有立即表明 pod 创建失败。违规的 podSpecs 将无法创建 pod。使用 `kubectl get deploy <DEPLOYMENT_NAME> -oyaml` 检查 Deployment 资源将暴露失败 pod 的 `.status.conditions` 元素中的消息，如下所示。

```yaml
...
status:
  conditions:
    - lastTransitionTime: "2022-01-20T01:02:08Z"
      lastUpdateTime: "2022-01-20T01:02:08Z"
      message: 'pods "test-688f68dc87-tw587" is forbidden: violates PodSecurity "restricted:latest":
        allowPrivilegeEscalation != false (container "test" must set securityContext.allowPrivilegeEscalation=false),
        unrestricted capabilities (container "test" must set securityContext.capabilities.drop=["ALL"]),
        runAsNonRoot != true (pod or container "test" must set securityContext.runAsNonRoot=true),
        seccompProfile (pod or container "test" must set securityContext.seccompProfile.type
        to "RuntimeDefault" or "Localhost")'
      reason: FailedCreate
      status: "True"
      type: ReplicaFailure
...
```

在 _audit_ 和 _warn_ 两种模式下，Pod 限制都不会阻止违规的 Pod 被创建和启动。但是，在这些模式下，当 Pod 以及创建 Pod 的对象中包含违规的 podSpec 时，分别会在 API 服务器审计日志事件上触发审计注释，并向 API 服务器客户端(如 _kubectl_)发出警告。下面是一个 `kubectl` _Warning_ 消息示例。

```bash
Warning: would violate PodSecurity "restricted:latest": allowPrivilegeEscalation != false (container "test" must set securityContext.allowPrivilegeEscalation=false), unrestricted capabilities (container "test" must set securityContext.capabilities.drop=["ALL"]), runAsNonRoot != true (pod or container "test" must set securityContext.runAsNonRoot=true), seccompProfile (pod or container "test" must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
deployment.apps/test created
```

PSA 的 _audit_ 和 _warn_ 模式在引入 PSS 时不会对集群操作产生负面影响，因此非常有用。

PSA 的操作模式并不互斥，可以累积使用。如下所示，可以在单个命名空间中配置多种模式。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: policy-test
  labels:
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

在上面的示例中，当应用 Deployment 时，会提供用户友好的警告和审计注释，同时也会在 Pod 级别强制执行违规情况。事实上，多个 PSA 标签可以使用不同的配置文件级别，如下所示。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: policy-test
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: restricted
```

在上面的示例中，PSA 被配置为允许创建满足 _baseline_ 配置文件级别的所有 pod，并对违反 _restricted_ 配置文件级别的 pod (以及创建 pod 的对象)发出 _warn_ 警告。这种方法有助于确定从 _baseline_ 切换到 _restricted_ 配置文件时可能产生的影响。

#### 现有 Pod

如果对使用了更严格 PSS 配置文件的命名空间进行修改，_audit_ 和 _warn_ 模式将产生适当的消息；但是，_enforce_ 模式不会删除 pod。下面是警告消息。

```bash
Warning: existing pods in namespace "policy-test" violate the new PodSecurity enforce level "restricted:latest"
Warning: test-688f68dc87-htm8x: allowPrivilegeEscalation != false, unrestricted capabilities, runAsNonRoot != true, seccompProfile
namespace/policy-test configured
```

#### 豁免

PSA 使用 _Exemptions_ 来排除对本应应用的 pod 的违规行为的执行。这些豁免如下所列。

- **用户名：** 来自具有豁免的经过身份验证 (或模拟) 用户名的请求将被忽略。

- **RuntimeClassNames：** 指定了豁免的运行时类名的 pod 和工作负载资源将被忽略。

- **命名空间：** 位于豁免命名空间中的 pod 和工作负载资源将被忽略。

这些豁免是作为 API 服务器配置的一部分，在 [PSA 准入控制器配置](https://kubernetes.io/docs/tasks/configure-pod-container/enforce-standards-admission-controller/#configure-the-admission-controller) 中静态应用的。

在 _Validating Webhook_ 实现中，豁免可以在 Kubernetes [ConfigMap](https://github.com/kubernetes/pod-security-admission/blob/master/webhook/manifests/20-configmap.yaml) 资源中配置，该资源将作为卷挂载到 [pod-security-webhook](https://github.com/kubernetes/pod-security-admission/blob/master/webhook/manifests/50-deployment.yaml) 容器中。

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pod-security-webhook
  namespace: pod-security-webhook
data:
  podsecurityconfiguration.yaml: |
    apiVersion: pod-security.admission.config.k8s.io/v1
    kind: PodSecurityConfiguration
    defaults:
      enforce: "restricted"
      enforce-version: "latest"
      audit: "restricted"
      audit-version: "latest"
      warn: "restricted"
      warn-version: "latest"
    exemptions:
      # 需要豁免的经过身份验证的用户名数组。
      usernames: []
      # 需要豁免的运行时类名数组。
      runtimeClasses: []
      # 需要豁免的命名空间数组。
      namespaces: ["kube-system","policy-test1"]
```

如上所示的 ConfigMap YAML 中，集群范围内的默认 PSS 级别已被设置为 _restricted_，适用于所有 PSA 模式：_audit_、_enforce_ 和 _warn_。这影响所有命名空间，除了被豁免的那些：`namespaces: ["kube-system","policy-test1"]`。此外，在下面看到的 _ValidatingWebhookConfiguration_ 资源中，_pod-security-webhook_ 命名空间也被豁免于配置的 PSS。

```yaml
...
webhooks:
  # 审计注解将以此名称为前缀
  - name: "pod-security-webhook.kubernetes.io"
    # 失败关闭的准入 Webhook 可能会带来操作上的挑战。
    # 您可能需要考虑使用 Ignore 的失败策略，但应该权衡安全性权衡。
    failurePolicy: Fail
    namespaceSelector:
      # 豁免 Webhook 本身以避免循环依赖。
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values: ["pod-security-webhook"]
...
```

!!! 注意

Pod 安全准入在 Kubernetes v1.25 版本中已经稳定发布。如果您想在默认启用该功能之前使用 Pod 安全准入功能，您需要安装动态准入控制器(变更 webhook)。安装和配置 webhook 的说明可以在[这里](https://github.com/kubernetes/pod-security-admission/tree/master/webhook)找到。

### 在策略代码和 Pod 安全标准之间做出选择

Pod 安全标准 (PSS) 是为了取代 Pod 安全策略 (PSP),通过提供一个内置于 Kubernetes 且不需要 Kubernetes 生态系统解决方案的解决方案而开发的。也就是说，策略代码 (PAC) 解决方案要灵活得多。

以下优缺点列表旨在帮助您就 pod 安全解决方案做出更明智的决定。

#### 策略代码(与 Pod 安全标准相比)

优点:

- 更灵活、更细粒度(如有需要，可以细化到资源的属性级别)
- 不仅仅关注于 pod，可以用于不同的资源和操作
- 不仅仅应用于命名空间级别
- 比 Pod 安全标准更成熟
- 决策可以基于 API 服务器请求负载中的任何内容，以及现有的集群资源和外部数据(取决于解决方案)
- 支持在验证之前对 API 服务器请求进行变更(取决于解决方案)
- 可以生成补充性策略和 Kubernetes 资源(取决于解决方案 - 从 pod 策略开始，Kyverno 可以[自动生成](https://kyverno.io/docs/writing-policies/autogen/)更高级别控制器的策略，如 Deployments。Kyverno 还可以通过使用[生成规则](https://kyverno.io/docs/writing-policies/generate/)在创建新资源或更新源时生成额外的 Kubernetes 资源。)
- 可以在 CICD 管道中提前使用，在调用 Kubernetes API 服务器之前(取决于解决方案)
- 可用于实现与安全无关的行为，如最佳实践、组织标准等
- 可用于非 Kubernetes 用例(取决于解决方案)
- 由于灵活性，用户体验可以根据用户需求进行调整

缺点:

- 不内置于 Kubernetes
- 更复杂的学习、配置和支持
- 编写策略可能需要新的技能/语言/能力

#### Pod 安全准入(与策略即代码相比)

优点:

- 内置于 Kubernetes
- 更简单的配置
- 无需使用新语言或编写策略
- 如果集群默认准入级别配置为 _privileged_，则可以使用命名空间标签让命名空间选择加入 pod 安全配置文件。

缺点:

- 不如策略即代码灵活或细粒度
- 只有 3 个限制级别
- 主要关注于 pod

#### 总结

如果您目前没有除 PSP 之外的 pod 安全解决方案，并且您所需的 pod 安全状态符合 Pod 安全标准 (PSS) 中定义的模型，那么采用 PSS 可能是一条更简单的途径，而不是使用基于策略的代码解决方案。但是，如果您的 pod 安全状态不符合 PSS 模型，或者您预计添加超出 PSS 定义范围的其他控制措施，那么基于策略的代码解决方案似乎更合适。

## 建议

### 使用多种 Pod 安全准入 (PSA) 模式以获得更好的用户体验

如前所述，PSA _enforce_ 模式可防止应用存在 PSS 违规的 pod，但不会阻止更高级别的控制器，例如 Deployment。实际上，Deployment 将成功应用，但不会有任何指示 pod 未能应用的信息。虽然您可以使用 _kubectl_ 检查 Deployment 对象，并从 PSA 中发现失败的 pod 消息，但用户体验可以更好。为了改善用户体验，应使用多种 PSA 模式(审计、强制执行、警告)。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: policy-test
  labels:
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

在上面的示例中，定义了 _enforce_ 模式，当尝试将存在 PSS 违规的 podSpec 的 Deployment 清单应用到 Kubernetes API 服务器时，Deployment 将成功应用，但 pod 不会。而且，由于还启用了 _audit_ 和 _warn_ 模式，API 服务器客户端将收到警告消息，API 服务器审计日志事件也将被注释上消息。

### 限制可以以特权模式运行的容器

如前所述，以特权模式运行的容器将继承主机上分配给root的所有Linux权能。很少有容器需要这些特权才能正常运行。有多种方法可用于限制容器的权限和权能。

!!! 注意

  Fargate是一种启动类型，可让您运行"无服务器"容器，容器的Pod在AWS管理的基础设施上运行。使用Fargate，您无法运行特权容器或将Pod配置为使用hostNetwork或hostPort。

### 不要以root身份在容器中运行进程

所有容器默认都是以root身份运行的。如果攻击者能够利用应用程序中的漏洞并获得对正在运行的容器的shell访问权限，这可能会带来问题。您可以通过多种方式缓解此风险。首先，从容器镜像中删除shell。其次，在Dockerfile中添加USER指令或以非root用户身份在Pod中运行容器。Kubernetes podSpec包括一组字段，位于`spec.securityContext`下，可让您指定运行应用程序的用户和/或组。这些字段分别是`runAsUser`和`runAsGroup`。

为了在Kubernetes podSpec中强制使用`spec.securityContext`及其关联元素，可以在集群中添加策略作为代码或Pod安全标准。这些解决方案允许您编写和/或使用策略或配置文件，在将其持久化到etcd之前，可以验证传入的Kubernetes API服务器请求负载。此外，策略作为代码解决方案还可以对传入请求进行变更，在某些情况下还可以生成新请求。

### 永远不要在Docker中运行Docker或在容器中挂载套接字

虽然这种方式方便地让您在Docker容器中构建/运行镜像，但您基本上是将节点的完全控制权交给了在容器中运行的进程。如果您需要在Kubernetes上构建容器镜像，请改用[Kaniko](https://github.com/GoogleContainerTools/kaniko)、[buildah](https://github.com/containers/buildah)或[CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/welcome.html)等构建服务。

!!! 提示

  用于CICD处理(如构建容器镜像)的Kubernetes集群应与运行更通用工作负载的集群隔离。

### 限制使用hostPath或者如果必须使用hostPath则限制可使用的前缀并将卷配置为只读

`hostPath`是一种将主机上的目录直接挂载到容器的卷。很少会有Pod需要这种类型的访问权限，但如果确实需要，您需要意识到其中的风险。默认情况下，以root身份运行的Pod将对hostPath暴露的文件系统具有写访问权限。这可能会允许攻击者修改kubelet设置、创建指向hostPath未直接暴露的目录或文件(如/etc/shadow)的符号链接、安装ssh密钥、读取挂载到主机的机密以及执行其他恶意操作。为了减轻hostPath带来的风险，请将`spec.containers.volumeMounts`配置为`readOnly`,例如:

```yaml
volumeMounts:
- name: hostPath-volume
    readOnly: true
    mountPath: /host-path
```

您还应该使用策略即代码解决方案来限制`hostPath`卷可以使用的目录，或者完全阻止使用`hostPath`。您可以使用Pod安全标准的_基线_或_受限_策略来防止使用`hostPath`。

有关特权升级危险的更多信息，请阅读Seth Art的博客[Bad Pods: Kubernetes Pod Privilege Escalation](https://labs.bishopfox.com/tech-blog/bad-pods-kubernetes-pod-privilege-escalation)。

### 为每个容器设置请求和限制以避免资源争用和DoS攻击

如果一个pod没有请求或限制，理论上它可以消耗主机上所有可用的资源。随着更多的pod被调度到节点上，节点可能会经历CPU或内存压力，这可能会导致Kubelet从节点中终止或逐出pod。虽然你无法完全防止这种情况发生，但设置请求和限制将有助于最小化资源争用，并减轻由于编写不当的应用程序消耗过多资源而带来的风险。

`podSpec`允许你为CPU和内存指定请求和限制。CPU被认为是一种可压缩资源，因为它可以被过度订阅。内存是不可压缩的，即它不能在多个容器之间共享。

当你为CPU或内存指定_请求_时，你实际上是在指定容器保证获得的_内存_量。Kubernetes汇总pod中所有容器的请求，以确定将pod调度到哪个节点上。如果容器超过了请求的内存量，如果节点上有内存压力，它可能会被终止。

_限制_是容器被允许消耗的最大CPU和内存资源量，并直接对应于为容器创建的cgroup的`memory.limit_in_bytes`值。超过内存限制的容器将被OOM杀死。如果容器超过其CPU限制，它将被节流。

!!! 提示

  当使用容器`resources.limits`时，强烈建议基于负载测试，以数据驱动和准确的方式确定容器资源使用情况(也称为资源占用)。如果没有准确可靠的资源占用，容器`resources.limits`可以适当增加。例如，`resources.limits.memory`可以比可观察到的最大值高出20-30%,以考虑潜在的内存资源限制不准确性。

Kubernetes 使用三种服务质量 (QoS) 类来对节点上运行的工作负载进行优先级排序。这些包括:

- guaranteed
- burstable
- best-effort

如果未设置限制和请求，则 pod 被配置为 _best-effort_（最低优先级）。当内存不足时，best-effort pod 将首先被杀死。如果在 pod 内的_所有_容器上设置了限制，或者请求和限制被设置为相同的非零值，则 pod 被配置为 _guaranteed_（最高优先级）。除非超过配置的内存限制，否则不会杀死 guaranteed pod。如果限制和请求被配置为不同的非零值，或者 pod 内的一个容器设置了限制而其他容器没有设置或为不同资源设置了限制，则 pod 被配置为 _burstable_（中等优先级）。这些 pod 有一些资源保证，但一旦超过其请求的内存就可能被杀死。

!!! 注意

  请求不会影响容器 cgroup 的 `memory_limit_in_bytes` 值;cgroup 限制被设置为主机上可用的内存量。然而，将请求值设置得太低可能会导致 kubelet 在节点出现内存压力时将 pod 列为终止目标。

| 类别 | 优先级 | 条件 | 杀死条件 |
| :-- | :-- | :-- | :-- |
| Guaranteed | 最高 | limit = request != 0  | 仅在超过内存限制时 |
| Burstable  | 中等  | limit != request != 0 | 如果超过请求内存可能会被杀死 |
| Best-Effort| 最低  | limit & request 未设置 | 当内存不足时首先被杀死 |

有关资源 QoS 的更多信息，请参阅 [Kubernetes 文档](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/)。

您可以通过在命名空间上设置[资源配额](https://kubernetes.io/docs/concepts/policy/resource-quotas/)或创建[限制范围](https://kubernetes.io/docs/concepts/policy/limit-range/)来强制使用请求和限制。资源配额允许您指定分配给命名空间的总资源量，例如CPU和RAM。当应用于命名空间时，它会强制您为部署到该命名空间的所有容器指定请求和限制。相比之下，限制范围可以让您更细粒度地控制资源分配。使用限制范围，您可以为命名空间内的每个Pod或每个容器设置CPU和内存资源的最小/最大值。您还可以使用它们来设置默认的请求/限制值(如果未提供)。

可以使用策略即代码解决方案来强制执行请求和限制，或者在创建命名空间时创建资源配额和限制范围。

### 不允许特权升级

特权升级允许进程更改其运行的安全上下文。Sudo就是一个很好的例子，具有SUID或SGID位的二进制文件也是如此。特权升级基本上是一种让用户以另一个用户或组的权限执行文件的方式。您可以通过实施一个策略即代码的变更策略来防止容器使用特权升级，该策略将`allowPrivilegeEscalation`设置为`false`,或者在`podSpec`中设置`securityContext.allowPrivilegeEscalation`。策略即代码策略还可用于在检测到不正确的设置时阻止API服务器请求成功。Pod安全标准也可用于防止Pod使用特权升级。

### 禁用ServiceAccount令牌挂载

对于不需要访问Kubernetes API的Pod，您可以在Pod规范上禁用自动挂载ServiceAccount令牌，或者对使用特定ServiceAccount的所有Pod禁用。

!!! 注意

禁用ServiceAccount挂载并不能阻止Pod访问Kubernetes API。要防止Pod访问Kubernetes API，您需要修改[EKS集群端点访问](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)并使用[NetworkPolicy](../network/#network-policy)来阻止Pod访问。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pod-no-automount
spec:
  automountServiceAccountToken: false
```

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sa-no-automount
automountServiceAccountToken: false
```

### 禁用服务发现

对于不需要查找或调用集群内服务的Pod，您可以减少提供给Pod的信息量。您可以将Pod的DNS策略设置为不使用CoreDNS，并且不将服务暴露为Pod命名空间中的环境变量。有关服务链接的更多信息，请参阅[Kubernetes环境变量文档][k8s-env-var-docs]。Pod的DNS策略默认值为"ClusterFirst"，它使用集群内DNS，而非默认值"Default"使用底层节点的DNS解析。有关更多信息，请参阅[Kubernetes Pod DNS策略文档][dns-policy]。

[k8s-env-var-docs]: https://kubernetes.io/docs/concepts/services-networking/service/#environment-variables
[dns-policy]: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-s-dns-policy

!!! 注意

  禁用服务链接和更改Pod的DNS策略并不能阻止Pod访问集群内DNS服务。攻击者仍然可以通过访问集群内DNS服务来枚举集群中的服务。(例如：`dig SRV *.*.svc.cluster.local @$CLUSTER_DNS_IP`)要防止集群内服务发现，请使用[NetworkPolicy](../network/#network-policy)来阻止Pod访问

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pod-no-service-info
spec:
    dnsPolicy: Default # "Default" 不是真正的默认值
    enableServiceLinks: false
```

### 为你的镜像配置只读根文件系统

为你的镜像配置只读根文件系统可以防止攻击者覆盖你的应用程序使用的文件系统上的二进制文件。如果你的应用程序需要写入文件系统，请考虑写入临时目录或附加并挂载卷。你可以通过设置 pod 的 SecurityContext 来强制执行这一点:

```yaml
...
securityContext:
  readOnlyRootFilesystem: true
...
```

可以使用策略代码和 Pod 安全标准来强制执行此行为。

!!! Info

  根据 [Kubernetes 中的 Windows 容器](https://kubernetes.io/docs/concepts/windows/intro/)，`securityContext.readOnlyRootFilesystem` 不能为在 Windows 上运行的容器设置为 `true`，因为注册表和系统进程需要在容器内写入访问权限才能运行。

## 工具和资源

- [Amazon EKS 安全沉浸式研讨会 - Pod 安全](https://catalog.workshops.aws/eks-security-immersionday/en-US/3-pod-security)
- [open-policy-agent/gatekeeper-library: OPA Gatekeeper 策略库](https://github.com/open-policy-agent/gatekeeper-library)一个可用于替代 PSP 的 OPA/Gatekeeper 策略库。
- [Kyverno 策略库](https://kyverno.io/policies/)
- 一组适用于 EKS 的常见 OPA 和 Kyverno [策略](https://github.com/aws/aws-eks-best-practices/tree/master/policies)。
- [基于策略的对策：第 1 部分](https://aws.amazon.com/blogs/containers/policy-based-countermeasures-for-kubernetes-part-1/)
- [基于策略的对策：第 2 部分](https://aws.amazon.com/blogs/containers/policy-based-countermeasures-for-kubernetes-part-2/)
- [Pod 安全策略迁移工具](https://appvia.github.io/psp-migration/)一个将 PSP 转换为 OPA/Gatekeeper、KubeWarden 或 Kyverno 策略的工具
- [SUSE 的 NeuVector](https://www.suse.com/neuvector/) 开源零信任容器安全平台，提供进程和文件系统策略以及准入控制规则。