# Kubernetes Cluster Task: 1 Control Plane + 1 Worker

Two-node Kubernetes cluster built with kubeadm on VMware Workstation with a GitHub Actions CI/CD pipeline 

## 1. Architecture

| Node | Hostname | IP | Role | Specs |
|---|---|---|---|---|
| VM 1 | `k8s-master` | 192.168.15.128 | control plane | 2 CPU, 4 GB |
| VM 2 | `k8s-worker` | 192.168.15.129 | worker | 2 CPU, 2 GB |

- OS: Ubuntu Server 24.04.3, NAT networking
- Kubernetes v1.36.5 (kubeadm), containerd runtime
- CNI: Calico v3.31.2, pod CIDR `10.244.0.0/16`
- Storage: local-path-provisioner (default StorageClass)

### Traffic flow

```
client -> <node-ip>:30090 (NodePort) -> nginx pod -> app:8080 (ClusterIP) -> one of 3 app pods
                                                                        |-> postgres:5432
                                                                        '-> redis:6379
```

Compose-to-Kubernetes mapping:

| Docker Compose | Kubernetes |
|---|---|
| nginx (published port) | Deployment + NodePort Service (30090), config in a ConfigMap |
| app-01/02/03 | one Deployment, 3 replicas, ClusterIP Service `app` |
| postgres + volume | StatefulSet + PVC, password in a Secret, init SQL in a ConfigMap |
| redis + volume | Deployment + PVC (AOF enabled) |
| internal backend network | NetworkPolicies |
| healthchecks | readiness/liveness probes |
| cpu/memory limits | resource requests/limits |

## 2. Cluster setup

Each step lists what it does and why.

### 2.1 Hostnames and name resolution (both nodes)
Why: the hostname becomes the Kubernetes node name.
```bash
sudo hostnamectl set-hostname k8s-master      # k8s-worker on the worker
echo -e "192.168.15.128 k8s-master\n192.168.15.129 k8s-worker" | sudo tee -a /etc/hosts
```

### 2.2 Static IPs (both nodes)
Why: a DHCP lease change would break the API server address and certificates.
```yaml
# /etc/netplan/50-cloud-init.yaml (use .129 on the worker)
network:
  version: 2
  ethernets:
    ens33:
      dhcp4: false
      addresses: [192.168.15.128/24]
      routes:
        - to: default
          via: 192.168.15.2
      nameservers:
        addresses: [192.168.15.2, 8.8.8.8]
```
```bash
sudo netplan apply
```

### 2.3 Node preparation (both nodes)
Why: kubelet refuses to run with swap on, and pod networking needs the kernel modules and sysctls.
```bash
sudo swapoff -a && sudo sed -i '/ swap /s/^/#/' /etc/fstab
printf "overlay\nbr_netfilter\n" | sudo tee /etc/modules-load.d/k8s.conf
sudo modprobe overlay br_netfilter
printf "net.bridge.bridge-nf-call-iptables=1\nnet.bridge.bridge-nf-call-ip6tables=1\nnet.ipv4.ip_forward=1\n" | sudo tee /etc/sysctl.d/k8s.conf
sudo sysctl --system
```

### 2.4 Container runtime (both nodes)
Why: Kubernetes needs a CRI runtime. `SystemdCgroup = true` makes containerd match kubelet's cgroup driver.
```bash
sudo apt-get update && sudo apt-get install -y containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
```

### 2.5 kubeadm, kubelet, kubectl (both nodes)
Why: kubeadm bootstraps the cluster, kubelet runs pods, kubectl is the CLI. Versions are held to avoid accidental upgrades.
```bash
sudo apt-get install -y apt-transport-https ca-certificates curl gpg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.36/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update && sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

### 2.6 Initialize the control plane (master)
Why: the pod CIDR must not overlap the node network (192.168.15.0/24). The advertise address pins the API server to the master's static IP.
```bash
sudo kubeadm init --apiserver-advertise-address=192.168.15.128 --pod-network-cidr=10.244.0.0/16
mkdir -p ~/.kube && sudo cp /etc/kubernetes/admin.conf ~/.kube/config && sudo chown $(id -u):$(id -g) ~/.kube/config
```

### 2.7 Join the worker
```bash
# on the master
sudo kubeadm token create --print-join-command
# run the printed command with sudo on the worker
```

### 2.8 Pod networking: Calico (master)
Why Calico: it enforces NetworkPolicy. Its default pool (`192.168.0.0/16`) overlaps the node network, so it is changed to match `kubeadm init`.
```bash
curl -O https://raw.githubusercontent.com/projectcalico/calico/v3.31.2/manifests/calico.yaml
sed -i 's|# - name: CALICO_IPV4POOL_CIDR|- name: CALICO_IPV4POOL_CIDR|; s|#   value: "192.168.0.0/16"|  value: "10.244.0.0/16"|' calico.yaml
kubectl apply -f calico.yaml
```

### 2.9 Storage (master)
Why: kubeadm ships no StorageClass, so PVCs would stay Pending.
```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.31/deploy/local-path-storage.yaml
kubectl patch sc local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

## 3. Verification

### 3.1 Both nodes Ready
```bash
kubectl get nodes -o wide
```
![node
### 3.2 Cross-node pod connectivity
One pod pinned to each node, then ping in both directions.
```bash
kubectl run pod-w --image=busybox:1.36 --overrides='{"spec":{"nodeName":"k8s-worker"}}' -- sleep 3600
kubectl run pod-m --image=busybox:1.36 --overrides='{"spec":{"nodeName":"k8s-master"}}' -- sleep 3600
kubectl get pods -o wide
kubectl exec pod-m -- ping -c3 <pod-w-ip>
kubectl exec pod-w -- ping -c3 <pod-m-ip>
```
Result: 0% packet loss both ways (pod IPs 10.244.235.196 on the master and 10.244.254.129 on the worker).
## 4. Application deployment

Manifests are in [`k8s/`](k8s/): `data.yaml` (postgres, redis, init SQL), `app.yaml`, `nginx.yaml`, `netpol.yaml`.

### 4.1 App image
```bash
docker build -t mohamedhamdy120/barq-app:v1 .
docker push mohamedhamdy120/barq-app:v1
```
The image is pushed to a public Docker Hub repo, so no pull secret is needed. Version tags are used instead of `latest` for reproducibility.

### 4.2 Namespace and secret
The password is created by command, never committed.
```bash
kubectl create namespace barq
kubectl -n barq create secret generic barq-secret \
  --from-literal=POSTGRES_PASSWORD='<PASSWORD>' \
  --from-literal=DATABASE_URL='postgresql://barq_app:<PASSWORD>@postgres:5432/barq_tasks'
```

### 4.3 Apply
```bash
kubectl apply -f k8s/data.yaml
kubectl apply -f k8s/app.yaml
kubectl apply -f k8s/nginx.yaml
kubectl apply -f k8s/netpol.yaml
kubectl -n barq get pods,svc -o wide
```
### 4.4 Load balancing check
```bash
for i in {1..6}; do curl -s 192.168.15.129:30090; echo; done
```
The `instance_id` field changes between responses, so requests are spread across the 3 replicas.
### 4.5 NetworkPolicy
Default deny for ingress in the `barq` namespace, then allow only: anyone to nginx, nginx to app (8080), app to postgres (5432) and redis (6379). This recreates the `internal` backend network from Compose.
```bash
kubectl -n barq run t --rm -it --image=busybox:1.36 --restart=Never -- nc -zvw3 postgres 5432   # times out (blocked)
```
## 5. Bonus: CI/CD pipeline (GitHub Actions)

Pipeline file: [`.github/workflows/ci-cd.yaml`](.github/workflows/ci-cd.yaml)

- **build** job (GitHub-hosted runner): builds the image and pushes it to Docker Hub, tagged with the commit SHA.
- **deploy** job (self-hosted runner on `k8s-master`): `kubectl set image` then `rollout status`.
- Why a self-hosted runner: GitHub's cloud runners cannot reach the private VM network. The runner connects outbound to GitHub, so no inbound access is needed.
- Why the commit SHA as tag: every deployment is traceable to a commit, and changing the tag triggers a rolling update.
- Credentials: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` are stored as GitHub Actions secrets.

Proof that a code change reaches the running app: the `version` value in `app/server.py` was bumped, pushed, and the new value appeared in `curl` output after the run.

![pipe

## 6. Issues hit and fixes

| Problem | Cause | Fix |
|---|---|---|
| Worker `NotReady` after reboot | Swap came back (`/swap.img`), kubelet refuses to run with swap | `swapoff -a` and comment the swap line in `/etc/fstab` |
| Pods `Pending` | Master tainted `NoSchedule`, worker unreachable | Fixed the worker; master taint kept on purpose |
| Image build failed in CI | `config/app.env` was gitignored | Committed the placeholder file (no real secret in it) |
| Pipeline did not trigger | Workflow `paths` filter excluded the change | Changed a file under `app/` |
| Code change not visible | `APP_MESSAGE` env var overrides the message in code | Changed the `version` field instead |

## 7. Notes and design decisions

- **Master taint kept:** app pods run on the worker, keeping workloads off the control plane.
- **nginx kept:** the Kubernetes Service already load-balances, but nginx preserves the edge behavior from the Docker stack (request IDs, JSON access logs, retries, timeouts).
- **Secrets:** the real DB password is created with `kubectl`, not stored in the repo. `config/app.env` only holds a `CHANGE_ME` placeholder; the app reads `DATABASE_URL` from the environment, which the Secret overrides.
- **Known issue:** `app/server.py` logs the full `DATABASE_URL`, password included, at startup. It should be masked before production use.
- **Single points of failure:** postgres and redis run as one instance each, as in the Docker task.
