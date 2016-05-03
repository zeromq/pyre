#e -*- mode: ruby -*-
# vi: set ft=ruby :

# This will setup a clean Ubuntu1404 LTS env with a python virtualenv called "pyre" for testing

$script = <<SCRIPT
apt-get update
add-apt-repository ppa:fkrull/deadsnakes-python2.7
apt-get update
apt-get install -y python-pip python-dev git htop virtualenvwrapper python2.7 python-virtualenv python-support cython
pip install requests --upgrade
pip install pip --upgrade
pip install vex
touch /home/vagrant/.vexrc
sudo -u vagrant virtualenv /home/vagrant/.virtualenvs/pyre
sudo -u vagrant vex --cwd /home/vagrant --config /home/vagrant/.vexrc --path /home/vagrant/.virtualenvs/pyre pip install cython==0.23.2 https://github.com/zeromq/pyzmq/archive/v15.2.0.tar.gz
sudo -u vagrant vex --cwd /vagrant --config /home/vagrant/.vexrc --path /home/vagrant/.virtualenvs/pyre python setup.py develop
SCRIPT

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"
VAGRANTFILE_LOCAL = 'Vagrantfile.local'

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = 'ubuntu/trusty64'
  config.vm.provision "shell", inline: $script
  config.vm.network "public_network"

  config.vm.provider :virtualbox do |vb|
    vb.customize ["modifyvm", :id, "--cpus", "2", "--ioapic", "on", "--memory", "1024" ]
  end

  if File.file?(VAGRANTFILE_LOCAL)
    external = File.read VAGRANTFILE_LOCAL
    eval external
  end
end

