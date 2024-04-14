# mmd-auto-trace-4

## 環境構築

```
(base) miu@garnet:~$ nvcc --version
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2022 NVIDIA Corporation
Built on Wed_Jun__8_16:49:14_PDT_2022
Cuda compilation tools, release 11.7, V11.7.99
Build cuda_11.7.r11.7/compiler.31442593_0
```

```
export PATH=/home/miu/anaconda3/envs/mat4/bin:$PATH
```

```
conda create -n mat4 python=3.10 -y
conda activate mat4
conda install pytorch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 pytorch-cuda=11.7 -c pytorch -c nvidia
```

```
import sys
import torch
pyt_version_str=torch.__version__.split("+")[0].replace(".", "")
version_str="".join([
    f"py3{sys.version_info.minor}_cu",
    torch.version.cuda.replace(".",""),
    f"_pyt{pyt_version_str}"
])

>>> version_str
'py310_cu117_pyt1131'
```

```
pip install pytorch3d -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu117_pyt1131/download.html
```

```
(mat4) miu@garnet:/mnt/c/MMD/mmd-auto-trace-4/src$

git submodule add https://github.com/miu200521358/WHAM.git WHAM
git submodule update --init --recursive
```

```
pip install -r WHAM/requirements.txt
pip install -v -e WHAM/third-party/ViTPose
(mat4) miu@garnet:/mnt/c/MMD/mmd-auto-trace-4$ pip install -r requirements.txt
```

## データ配置

- checkpoints
- dataset














## submodule

```
git submodule add https://github.com/miu200521358/WHAM.git WHAM
git submodule update --init --recursive
```

```
conda remove -n wham --all

sudo apt-get --purge remove "*cuda*" "*cublas*" "*cufft*" "*cufile*" "*curand*" \
 "*cusolver*" "*cusparse*" "*gds-tools*" "*npp*" "*nvjpeg*" "nsight*" "*nvvm*"
sudo apt-get --purge remove "*nvidia*" "libxnvctrl*"
sudo apt-get autoremove
```

```
(wham) miu@garnet:/mnt/c/MMD/mmd-auto-trace-4$

WSL用ドライバのインストール
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-wsl-ubuntu.pin
sudo mv cuda-wsl-ubuntu.pin /etc/apt/preferences.d/cuda-repository-pin-600
sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/7fa2af80.pub
sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/ /"
sudo apt-get update
sudo apt-get -y install cuda-11-3

wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin
sudo mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/11.3.1/local_installers/cuda-repo-ubuntu2004-11-3-local_11.3.1-465.19.01-1_amd64.deb
sudo dpkg -i cuda-repo-ubuntu2004-11-3-local_11.3.1-465.19.01-1_amd64.deb
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-11-3

export CUDA_PATH=/usr/local/cuda-11.3
echo 'export CUDA_PATH=/usr/local/cuda-11.3' >> ${HOME}/.bashrc
export LD_LIBRARY_PATH=/usr/local/cuda-11.3/lib64:${LD_LIBRARY_PATH}
echo 'export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/cuda-11.3/lib64' >> ${HOME}/.bashrc
export PATH=/usr/local/cuda-11.3/bin:${PATH}
echo 'export PATH=${PATH}:/usr/local/cuda-11.3/bin' >> ${HOME}/.bashrc

echo $PATH
echo $LD_LIBRARY_PATH
echo $CUDA_HOME


conda create -n wham python=3.9 -y
conda activate wham
conda install pytorch==1.11.0 torchvision==0.12.0 torchaudio==0.11.0 cudatoolkit=11.3 -c pytorch -y
conda install -c fvcore -c iopath -c conda-forge fvcore iopath -y

pip install pytorch3d -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py39_cu113_pyt1110/download.html
pip install -r WHAM/requirements.txt
pip install -v -e WHAM/third-party/ViTPose

cd WHAM/third-party/DPVO
wget https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.zip
unzip eigen-3.4.0.zip -d thirdparty && rm -rf eigen-3.4.0.zip
conda install pytorch-scatter=2.0.9 -c rusty1s -y
conda install cudatoolkit-dev=11.3.1 -c conda-forge -y
conda install -c conda-forge gxx=9.5 -y
pip install ninja
pip install .

git clone https://github.com/NVIDIA/apex
cd apex
pip install -v --disable-pip-version-check --no-cache-dir --no-build-isolation --config-settings "--build-option=--cpp_ext" --config-settings "--build-option=--cuda_ext" ./


bash fetch_demo_data.sh
python demo.py --video examples/IMG_9732.mov --visualize --save_pkl --run_smplify

```



















