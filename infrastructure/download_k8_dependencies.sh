#!/bin/bash

set -e

# ------------------------------
# Variables
# ------------------------------
OS_VERSION="xUbuntu_20.04"     # Change to xUbuntu_22.04 for Ubuntu 22.04
K8S_VERSION="1.29"             # Match this with kubeadm/kubelet version
ARCH="amd64"
KUBE_VERSION_STABLE=$(curl -s https://dl.k8s.io/release/stable.txt)

# ------------------------------
# Disable Swap
# ------------------------------
echo "[TASK 1] Disabling swap"
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

# ------------------------------
# Enable Required Kernel Modules
# ------------------------------
echo "[TASK 2] Loading kernel modules"
sudo modprobe overlay
sudo modprobe br_netfilter

# ------------------------------
# Apply Sysctl Settings
# ------------------------------
echo "[TASK 3] Applying sysctl settings"
cat <<EOF | sudo tee /etc/sysctl.d/kubernetes.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system

# ------------------------------
# Install CRI-O Runtime
# ------------------------------
echo "[TASK 4] Installing CRI-O runtime"
sudo mkdir -p /usr/share/keyrings

echo "deb [signed-by=/usr/share/keyrings/libcontainers-archive-keyring.gpg] \
https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/${OS_VERSION}/ /" | \
sudo tee /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list

echo "deb [signed-by=/usr/share/keyrings/crio-archive-keyring.gpg] \
https://download.opensuse.org/repositories/devel:kubic:cri-o:/${K8S_VERSION}/${OS_VERSION}/ /" | \
sudo tee /etc/apt/sources.list.d/devel:kubic:cri-o:${K8S_VERSION}.list

curl -fsSL https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/${OS_VERSION}/Release.key | \
gpg --dearmor -o libcontainers-archive-keyring.gpg && sudo mv libcontainers-archive-keyring.gpg /usr/share/keyrings/

curl -fsSL https://download.opensuse.org/repositories/devel:/kubic:/cri-o:/${K8S_VERSION}/${OS_VERSION}/Release.key | \
gpg --dearmor -o crio-archive-keyring.gpg && sudo mv crio-archive-keyring.gpg /usr/share/keyrings/

sudo apt-get update
sudo apt-get install -y cri-o cri-o-runc
sudo systemctl daemon-reexec
sudo systemctl enable crio --now

# ------------------------------
# Install Kubernetes Tools
# ------------------------------
echo "[TASK 5] Installing kubeadm, kubelet, kubectl"
sudo apt-get install -y apt-transport-https ca-certificates curl
sudo curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg

echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] \
https://apt.kubernetes.io/ kubernetes-xenial main" | \
sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# ------------------------------
# Start kubelet
# ------------------------------
echo "[TASK 6] Enabling kubelet"
sudo systemctl enable kubelet

# ------------------------------
# Verify Versions
# ------------------------------
echo "[INFO] Installed versions:"
kubeadm version
kubelet --version
kubectl version --client
crio --version

echo "[DONE] Kubernetes prerequisites are installed."