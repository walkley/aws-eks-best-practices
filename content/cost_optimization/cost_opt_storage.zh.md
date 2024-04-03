---
date: 2023-10-31
authors: 
  - Chance Lee
---
# 成本优化 - 存储

## 概述

在某些场景下，您可能需要运行需要保留数据的应用程序，无论是短期还是长期。对于此类用例，可以定义卷并由Pod挂载，以便其容器可以访问不同的存储机制。Kubernetes支持不同类型的[卷](https://kubernetes.io/docs/concepts/storage/volumes/)用于临时和持久存储。存储的选择在很大程度上取决于应用程序需求。对于每种方法，都有成本影响，下面详细介绍的做法将帮助您在需要某种形式存储的EKS环境中实现工作负载的成本效率。


## 临时卷

临时卷适用于需要临时本地卷但不需要在重启后保留数据的应用程序。这包括对临时空间、缓存和只读输入数据(如配置数据和密钥)的需求。您可以在[此处](https://kubernetes.io/docs/concepts/storage/ephemeral-volumes/)找到有关Kubernetes临时卷的更多详细信息。大多数临时卷(例如emptyDir、configMap、downwardAPI、secret、hostpath)都由本地附加的可写设备(通常是根磁盘)或RAM支持，因此选择最具成本效益和性能的主机卷很重要。


### 使用EBS卷

*我们建议从[gp3](https://aws.amazon.com/ebs/general-purpose/)开始作为主机根卷。*它是Amazon EBS提供的最新通用SSD卷，与gp2卷相比每GB的价格也更低(最高20%)。


### 使用Amazon EC2实例存储

[Amazon EC2 实例存储](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html)为您的 EC2 实例提供临时块级存储。EC2 实例存储提供的存储可通过物理连接到主机的磁盘访问。与 Amazon EBS 不同，您只能在启动实例时附加实例存储卷，并且这些卷仅在实例生存期内存在。它们无法分离并重新附加到其他实例。您可以在[此处](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html)了解更多关于 Amazon EC2 实例存储的信息。*实例存储卷不会产生额外费用。*这使它们(实例存储卷)比具有大型 EBS 卷的一般 EC2 实例_更具成本效益_。

要在 Kubernetes 中使用本地存储卷，您应该[使用 Amazon EC2 用户数据](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-add-user-data.html)对磁盘进行分区、配置和格式化，以便可以将卷作为 pod 规范中的 [HostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath) 进行挂载。或者，您可以利用 [Local Persistent Volume Static Provisioner](https://github.com/kubernetes-sigs/sig-storage-local-static-provisioner) 来简化本地存储管理。Local Persistent Volume 静态供应器允许您通过标准的 Kubernetes PersistentVolumeClaim (PVC) 接口访问本地实例存储卷。此外，它将提供包含节点亲和性信息的 PersistentVolumes (PVs),以将 Pod 调度到正确的节点。尽管它使用 Kubernetes PersistentVolumes，但 EC2 实例存储卷本质上是临时的。写入临时磁盘的数据仅在实例生存期内可用。实例终止时，数据也会终止。请参阅此[博客](https://aws.amazon.com/blogs/containers/eks-persistent-volumes-for-instance-store/)以了解更多详细信息。

请注意，当使用Amazon EC2实例存储卷时，总IOPS限制是与主机共享的，并且它将Pod绑定到特定主机。在采用Amazon EC2实例存储卷之前，您应该彻底审查工作负载要求。

## 持久卷

Kubernetes通常与运行无状态应用程序相关联。但是，在某些情况下，您可能需要运行需要从一个请求保留持久数据或信息到下一个请求的微服务。数据库就是这种用例的常见示例。但是，Pod及其中的容器或进程都是短暂的。为了在Pod生命周期之外持久化数据，您可以使用PV来定义对独立于Pod的特定位置存储的访问。*与PV相关的成本在很大程度上取决于所使用的存储类型以及应用程序如何使用它。*

有不同类型的存储选项支持Amazon EKS上的Kubernetes PV，列在[这里](https://docs.aws.amazon.com/eks/latest/userguide/storage.html)。下面介绍的存储选项包括Amazon EBS、Amazon EFS、Amazon FSx for Lustre和Amazon FSx for NetApp ONTAP。

### Amazon Elastic Block Store (EBS) 卷

Amazon EBS 卷可以作为 Kubernetes PV 使用，提供块级存储卷。这些卷非常适合依赖随机读写和吞吐量密集型应用程序的数据库，这些应用程序执行长时间连续的读写操作。[Amazon Elastic Block Store 容器存储接口 (CSI) 驱动程序](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)允许 Amazon EKS 集群管理 Amazon EBS 卷的生命周期，用于持久卷。容器存储接口可以实现和促进 Kubernetes 与存储系统之间的交互。当 CSI 驱动程序部署到您的 EKS 集群时，您可以通过本机 Kubernetes 存储资源（如持久卷 (PV)、持久卷声明 (PVC) 和存储类 (SC)）访问其功能。此[链接](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/tree/master/examples/kubernetes)提供了如何使用 Amazon EBS CSI 驱动程序与 Amazon EBS 卷交互的实际示例。

#### 选择合适的卷

*我们建议使用最新一代的块存储 (gp3)，因为它在价格和性能之间提供了合适的平衡*。它还允许您独立于卷大小扩展卷 IOPS 和吞吐量，而无需预置额外的块存储容量。如果您当前正在使用 gp2 卷，我们强烈建议迁移到 gp3 卷。此[博客](https://aws.amazon.com/blogs/containers/migrating-amazon-eks-clusters-from-gp2-to-gp3-ebs-volumes/)解释了如何在 Amazon EKS 集群上从 *gp2* 迁移到 *gp3*。

当您有需要更高性能和比单个 [gp3 卷](https://aws.amazon.com/ebs/general-purpose/)更大容量的应用程序时，您应该考虑使用 [io2 块快速](https://aws.amazon.com/ebs/provisioned-iops/)。这种存储类型非常适合您最大、I/O 密集型和关键任务部署，如 SAP HANA 或其他具有低延迟要求的大型数据库。请记住，实例的 EBS 性能受实例性能限制的约束，因此并非所有实例都支持 io2 块快速卷。您可以在此 [文档](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/provisioned-iops.html) 中查看支持的实例类型和其他注意事项。

*单个 gp3 卷最多可支持 16，000 IOPS、1,000 MiB/s 最大吞吐量、最大 16TiB。最新一代 Provisioned IOPS SSD 卷可提供高达 256，000 IOPS、4,000 MiB/s 吞吐量和 64TiB。*

在这些选项中，您应该根据应用程序的需求来最佳调整存储性能和成本。


#### 持续监控和优化

了解您的应用程序的基线性能并对所选卷进行监控非常重要，以检查它是否满足您的要求/期望或者是否过度供应(例如，预配置的 IOPS 未被完全利用的情况)。

您可以从一开始就逐步增加卷的大小，而不是一次性分配大卷。您可以使用 Amazon Elastic Block Store CSI 驱动程序 (aws-ebs-csi-driver) 中的 [卷调整大小](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/tree/master/examples/kubernetes/resizing)功能动态调整卷大小。*请记住，您只能增加 EBS 卷的大小。*

要识别和删除任何悬空的 EBS 卷，您可以使用 [AWS 可信赖顾问的成本优化类别](https://docs.aws.amazon.com/awssupport/latest/user/cost-optimization-checks.html)。此功能可帮助您识别未附加的卷或在一段时间内写入活动非常低的卷。有一个名为 [Popeye](https://github.com/derailed/popeye) 的云原生开源只读工具，它可以扫描实时 Kubernetes 集群并报告已部署资源和配置的潜在问题。例如，它可以扫描未使用的 PV 和 PVC，并检查它们是否已绑定或是否存在任何卷挂载错误。

有关监控的深入探讨，请参阅 [EKS 成本优化可观察性指南](https://aws.github.io/aws-eks-best-practices/cost_optimization/cost_opt_observability/)。

您可以考虑的另一个选择是 [AWS Compute Optimizer Amazon EBS 卷建议](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-ebs-recommendations.html)。此工具可自动识别所需的最佳卷配置和正确的性能级别。例如，它可用于基于过去 14 天的最大利用率确定预配置 IOPS、卷大小和 EBS 卷类型的最佳设置。它还量化了其建议所带来的潜在每月成本节省。您可以查看此 [博客](https://aws.amazon.com/blogs/storage/cost-optimizing-amazon-ebs-volumes-using-aws-compute-optimizer/) 以了解更多详细信息。

#### 备份保留策略

您可以通过创建时间点快照来备份 Amazon EBS 卷上的数据。Amazon EBS CSI 驱动程序支持卷快照。您可以按照[此处](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/blob/master/examples/kubernetes/snapshot/README.md)概述的步骤了解如何创建快照和还原 EBS PV。

后续快照是增量备份，这意味着只有自上次快照后设备上发生更改的块才会被保存。这将最小化创建快照所需的时间，并通过不复制数据来节省存储成本。但是，如果没有适当的保留策略，旧EBS快照数量的增长可能会在大规模运营时导致意外成本。如果您直接通过AWS API备份Amazon EBS卷，您可以利用[Amazon Data Lifecycle Manager](https://aws.amazon.com/ebs/data-lifecycle-manager/),它为Amazon Elastic Block Store (EBS)快照和基于EBS的Amazon Machine Images (AMIs)提供了自动化、基于策略的生命周期管理解决方案。控制台可以更轻松地自动创建、保留和删除EBS快照和AMI。

!!! note
    目前无法通过Amazon EBS CSI驱动程序使用Amazon DLM。

在Kubernetes环境中，您可以利用一个名为[Velero](https://velero.io/)的开源工具来备份您的EBS持久卷。您可以在调度作业时设置TTL标志来使备份过期。这是Velero的一个[指南](https://velero.io/docs/v1.12/how-velero-works/#set-a-backup-to-expire)示例。


### Amazon Elastic File System (EFS)

[Amazon Elastic File System (EFS)](https://aws.amazon.com/efs/)是一个无服务器、完全弹性的文件系统，允许您使用标准文件系统接口和文件系统语义共享文件数据，适用于广泛的工作负载和应用程序。工作负载和应用程序的示例包括Wordpress和Drupal、JIRA和Git等开发人员工具，以及共享笔记本系统(如Jupyter)和主目录。

Amazon EFS 的主要优势之一是可以被分布在多个节点和多个可用区的多个容器挂载。另一个优势是您只需为使用的存储付费。EFS 文件系统会随着您添加和删除文件而自动增长和缩小，从而消除了容量规划的需求。

要在 Kubernetes 中使用 Amazon EFS，您需要使用 Amazon Elastic File System Container Storage Interface (CSI) 驱动程序 [aws-efs-csi-driver](https://github.com/kubernetes-sigs/aws-efs-csi-driver)。目前，该驱动程序可以动态创建[访问点](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html)。但是，Amazon EFS 文件系统必须先被配置，并作为 Kubernetes 存储类参数的输入提供。

#### 选择合适的 EFS 存储类

Amazon EFS 提供[四种存储类](https://docs.aws.amazon.com/efs/latest/ug/storage-classes.html)。

两种标准存储类:

* Amazon EFS Standard
* [Amazon EFS Standard-Infrequent Access](https://aws.amazon.com/blogs/aws/optimize-storage-cost-with-reduced-pricing-for-amazon-efs-infrequent-access/) (EFS Standard-IA)

两种单区存储类:

* [Amazon EFS One Zone](https://aws.amazon.com/blogs/aws/new-lower-cost-one-zone-storage-classes-for-amazon-elastic-file-system/)
* Amazon EFS One Zone-Infrequent Access (EFS One Zone-IA)

不经常访问 (IA) 存储类针对每天不被访问的文件进行了成本优化。通过 Amazon EFS 生命周期管理，您可以将在生命周期策略持续时间 (7、14、30、60 或 90 天) 内未被访问的文件移至 IA 存储类，*与 EFS Standard 和 EFS One Zone 存储类相比，可降低高达 92% 的存储成本*。

使用 EFS Intelligent-Tiering,生命周期管理会监控您的文件系统的访问模式，并自动将文件移至最佳存储类。

!!! note
    aws-efs-csi-driver 目前无法控制更改存储类、生命周期管理或智能分层。这些应该在 AWS 控制台或通过 EFS API 手动设置。

!!! note
    aws-efs-csi-driver 与基于 Window 的容器镜像不兼容。

!!! note
    当启用 *vol-metrics-opt-in*（发出卷指标）时，存在已知的内存问题，这是由于 [DiskUsage](https://github.com/kubernetes/kubernetes/blob/ee265c92fec40cd69d1de010b477717e4c142492/pkg/volume/util/fs/fs.go#L66) 函数消耗的内存量与文件系统的大小成正比。*目前，我们建议在大型文件系统上禁用 `--vol-metrics-opt-in` 选项，以避免消耗过多内存。这里有一个 github 问题 [链接](https://github.com/kubernetes-sigs/aws-efs-csi-driver/issues/1104) 提供更多详细信息。*


### Amazon FSx for Lustre

Lustre 是一种高性能并行文件系统，通常用于需要高达数百 GB/s 的吞吐量和亚毫秒级别的每个操作延迟的工作负载。它用于机器学习训练、金融建模、HPC 和视频处理等场景。[Amazon FSx for Lustre](https://aws.amazon.com/fsx/lustre/) 提供完全托管的共享存储，具有可扩展性和性能，并与 Amazon S3 无缝集成。

您可以使用由 FSx for Lustre 支持的 Kubernetes 持久存储卷，在 Amazon EKS 或您在 AWS 上的自管理 Kubernetes 集群中使用 [FSx for Lustre CSI 驱动程序](https://github.com/kubernetes-sigs/aws-fsx-csi-driver)。有关更多详细信息和示例，请参阅 [Amazon EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/fsx-csi.html)。

#### 与 Amazon S3 的链接

建议将高度持久的长期数据存储库（位于Amazon S3上）与您的FSx for Lustre文件系统链接。一旦链接，大型数据集将根据需要从Amazon S3延迟加载到FSx for Lustre文件系统。您还可以运行分析并将结果返回到S3，然后删除您的[Lustre]文件系统。

#### 选择合适的部署和存储选项

FSx for Lustre提供不同的部署选项。第一个选项称为*scratch*，它不复制数据，而第二个选项称为*persistent*，顾名思义，它会持久化数据。

第一个选项(*scratch*)可用于*减少临时短期数据处理的成本。*持久部署选项_旨在长期存储_，它会自动在AWS可用区内复制数据。它还支持SSD和HDD存储。

您可以在FSx for lustre文件系统的Kubernetes StorageClass的参数中配置所需的部署类型。这里有一个[链接](https://github.com/kubernetes-sigs/aws-fsx-csi-driver/tree/master/examples/kubernetes/dynamic_provisioning#edit-storageclass)提供了示例模板。

!!! note
    对于延迟敏感型工作负载或需要最高IOPS/吞吐量的工作负载，您应该选择SSD存储。对于以吞吐量为中心且不太敏感延迟的工作负载，您应该选择HDD存储。

#### 启用数据压缩

您还可以通过指定"LZ4"作为数据压缩类型来启用文件系统上的数据压缩。一旦启用，所有新写入的文件在写入磁盘之前都会在FSx for Lustre上自动压缩，读取时会自动解压缩。LZ4数据压缩算法是无损的，因此可以从压缩数据完全重构原始数据。

您可以在 FSx for lustre 文件系统的 Kubernetes StorageClass 中的参数下配置 LZ4 作为数据压缩类型。当值设置为 NONE 时（这是默认值），压缩将被禁用。此[链接](https://github.com/kubernetes-sigs/aws-fsx-csi-driver/tree/master/examples/kubernetes/dynamic_provisioning#edit-storageclass)提供了示例模板。

!!! note
    Amazon FSx for Lustre 与基于 Window 的容器镜像不兼容。


### Amazon FSx for NetApp ONTAP

[Amazon FSx for NetApp ONTAP](https://aws.amazon.com/fsx/netapp-ontap/) 是一种基于 NetApp 的 ONTAP 文件系统构建的全托管共享存储。FSx for ONTAP 提供功能丰富、快速且灵活的共享文件存储，可广泛访问运行在 AWS 或本地的 Linux、Windows 和 macOS 计算实例。

Amazon FSx for NetApp ONTAP 支持两个存储层：*1/主存储层*和*2/容量池存储层*。

*主存储层*是一个基于高性能 SSD 的预配置层，用于活跃的、延迟敏感的数据。完全弹性的*容量池存储层*针对不常访问的数据进行了成本优化，可自动扩展为数据分层时的容量，并提供了几乎无限的 PB 级容量。您可以在容量池存储上启用数据压缩和重复数据删除功能，进一步减少数据占用的存储容量。NetApp 原生的基于策略的 FabricPool 功能持续监控数据访问模式，自动在存储层之间双向传输数据，以优化性能和成本。

NetApp 的 Astra Trident 使用 CSI 驱动程序提供动态存储编排，允许 Amazon EKS 集群管理由 Amazon FSx for NetApp ONTAP 文件系统支持的持久卷 PV 的生命周期。要开始使用，请参阅 Astra Trident 文档中的[将 Astra Trident 与 Amazon FSx for NetApp ONTAP 一起使用](https://docs.netapp.com/us-en/trident/trident-use/trident-fsx.html)。


## 其他注意事项

### 最小化容器镜像大小

一旦容器部署完成，容器镜像就会作为多个层缓存在主机上。通过减小镜像的大小，可以减少主机上所需的存储量。

从一开始就使用精简的基础镜像，如 [scratch](https://hub.docker.com/_/scratch) 镜像或 [distroless](https://github.com/GoogleContainerTools/distroless) 容器镜像(只包含您的应用程序及其运行时依赖项),*除了可以减少存储成本外，还可以带来其他附加好处，如减小攻击面积和缩短镜像拉取时间。*

您还应该考虑使用开源工具，如 [Slim.ai](https://www.slim.ai/docs/quickstart),它提供了一种简单、安全的方式来创建最小化的镜像。

多层软件包、工具、应用程序依赖项和库很容易使容器镜像体积膨胀。通过使用多阶段构建，您可以选择性地从一个阶段复制构件到另一个阶段，从最终镜像中排除所有不必要的内容。您可以在[这里](https://docs.docker.com/get-started/09_image_best/)查看更多镜像构建最佳实践。

另一个需要考虑的是缓存镜像的持续时间。当使用了一定量的磁盘空间时，您可能需要从镜像缓存中清理陈旧的镜像。这样做有助于确保主机有足够的空间进行操作。默认情况下，[kubelet](https://kubernetes.io/docs/reference/generated/kubelet) 每五分钟对未使用的镜像进行垃圾收集，每分钟对未使用的容器进行垃圾收集。

*要为未使用的容器和镜像垃圾收集配置选项，请使用[配置文件](https://kubernetes.io/docs/tasks/administer-cluster/kubelet-config-file/)调整 kubelet，并使用 [`KubeletConfiguration`](https://kubernetes.io/docs/reference/config-api/kubelet-config.v1beta1/) 资源类型更改与垃圾收集相关的参数。*

你可以在 Kubernetes [文档](https://kubernetes.io/docs/concepts/architecture/garbage-collection/#containers-images)中了解更多相关信息。