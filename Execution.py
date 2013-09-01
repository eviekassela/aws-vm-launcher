'''
Created on Sep 1, 2013

@author: eviek.
'''
#!/usr/bin/env python

import sys, time
import paramiko
from Instance import InstanceHandler

class Executioner:
    
    def __init__(self):
        self.instances = InstanceHandler()
        self.key = str('/tmp/' + self.instances.key + '.pem')
    
    def load_data(self):
        # Transfer data : transfer to 1 host and scp from there to other hosts using private ip
        print "Transferring data to servers"
        pkey = paramiko.RSAKey.from_private_key_file(self.key)
        try:
            transport = paramiko.Transport((self.hosts[0], 22))
            transport.connect(username = 'ubuntu', pkey=pkey)
            transport.open_channel("session", self.hosts[0], "localhost")
            sftp = paramiko.SFTPClient.from_transport(transport)
            # Send file to host[0]
            sftp.put("testfile","/home/ubuntu/testfile")
            sftp.put("run.sh", "/home/ubuntu/run.sh")
            # Send private key for access to other hosts
            sftp.put(self.key,self.key)
            sftp.close()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.hosts[0], username='ubuntu', key_filename=self.key)
            # Set permissions to be able to use the key
            stdin, stdout, stderr = ssh.exec_command('chmod 700 ' + self.key)
            stdin, stdout, stderr = ssh.exec_command('chmod a+x run.sh')
            # Copy data to other hosts with scp
            # NOTE: only for first connection in other hosts no StrictHostKeyChecking!
            for ip in self.ips[1:]:
                stdin, stdout, stderr = ssh.exec_command('scp -o StrictHostKeyChecking=no -i '
                                                         +self.key+' testfile ubuntu@'+ip+':~/')
                stdin, stdout, stderr = ssh.exec_command('scp -i '+self.key+' run.sh ubuntu@'+ip+':~/')
#                print stdout.readlines(), stderr.readlines()
        except:
            print "An error occurred while transferring data"
            self.instances.terminate()
            raise
        ssh.close()
        print "Transfer complete"
        
    def get_results(self):
        print "Copying results from remote servers"
        pkey = paramiko.RSAKey.from_private_key_file(self.key)
        for host in self.hosts:
            try:
                transport = paramiko.Transport((host, 22))
                transport.connect(username = 'ubuntu', pkey=pkey)
                transport.open_channel("session", host, "localhost")
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.get("/home/ubuntu/testfile","resultfile_"+host)
                sftp.close()
            except:
                print "An error occurred while receiving results. Retrieve them manually and handle"
                print "remaining instances' termination."
                raise
        print "Transfer complete"
    
    def start(self):
        self.hosts, self.ips = self.instances.launch()
        # Wait for servers to start all services
        print "Wait 1 minute for servers to be ready"
        time.sleep(60)
        self.load_data()
        # Execute commands in all hosts
        print "Starting execution"
        for host in self.hosts:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(host, username='ubuntu', key_filename=self.key)
                # Execute command
                stdin, stdout, stderr = ssh.exec_command('./run.sh')
                print stdout.readlines()
#                channel = stdout.channel
#                status = channel.recv_exit_status()
            except:
                print "An error occurred while executing commands"
                self.instances.terminate()
                raise
            ssh.close()
        print "Finished execution"
        self.get_results()
        self.instances.terminate()
        
if __name__ == "__main__":    
    execution = Executioner()
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            execution.start()
        elif 'stop' == sys.argv[1]:
            print "Not yet implemented"
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop" % sys.argv[0]
        sys.exit(2)
    sys.exit(0)
