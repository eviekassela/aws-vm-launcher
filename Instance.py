'''
Created on Sep 3, 2013

@author: eviek.
'''
#!/usr/bin/env python

import boto.ec2
import sys, os, time
from ConfigParser import ConfigParser

class InstanceHandler:
    
    def __init__(self):
        # Read the configuration properties
        cfg = ConfigParser()
        cfg.read("Instance.properties")
        self.aws_access_key_id = cfg.get("config", "aws_access_key_id")
        self.aws_secret_access_key = cfg.get("config", "aws_secret_access_key")
        self.region = cfg.get("config", "region_name")
        self.key = cfg.get("config", "key_pair")
        self.image = cfg.get("config", "image")
        self.count = cfg.get("config", "instance_count")
        self.instance_type = cfg.get("config", "instance_type")
        self.security_group = cfg.get("config", "security_group")
        self.hostname_template = cfg.get("config", "hostname_template")
        self.availabity_zone = cfg.get("config", "availabity_zone")
        self.instances = []
    
    def launch(self):
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        # Create private key and save to disk
        keypair = conn.create_key_pair(self.key)
        keypair.save("/tmp")
        # Create simple security group to allow ssh connections
        self.group = conn.create_security_group(name=self.security_group, description=self.security_group)
        self.group.authorize('tcp', 22, 22, '0.0.0.0/0')
        # Launch instances
        reservation = conn.run_instances(self.image, min_count=self.count, max_count=self.count,
                                         key_name=self.key, security_groups=[self.group], 
                                         instance_type=self.instance_type, placement=self.availabity_zone)
        # Wait for all instances to be up and running
        self.instances = reservation.instances
        for instance in self.instances:
            status = instance.update()
            while status == 'pending':
                time.sleep(2)
                status = instance.update()
        # Name and list new instances 
        count = 0
        hosts = []
        ips = []
        print "Launched new instances:"
        print "Name\t\tInstance\tHostname"
        for instance in self.instances:
            count += 1
            name = self.hostname_template + str(count)
            instance.add_tag("Name", name)
            print name + "\t" + instance.id + "\t" + instance.public_dns_name
            hosts.append(instance.public_dns_name)
            ips.append(instance.private_ip_address)
        print 'Private key path: /tmp/' + self.key + '.pem'
        conn.close()
        # Return list of hostnames
        return hosts, ips
    
    def terminate(self):
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        if not self.instances:
            # Get reservations with running instances
            reservations = conn.get_all_instances(filters={'instance-state-name': 'running'})
            if reservations:
                for r in reservations:
                    self.instances = self.instances + r.instances
                sys.stdout.write("Running instances: ")
                sys.stdout.write(self.instances[0].id)
                for instance in self.instances[1:]:
                    sys.stdout.write(", " + instance.id)
                sys.stdout.write("\nTerminate all running instances? [Y/n] ")
                answer = raw_input().lower()
                while answer not in ["", "y", "ye", "yes", "n", "no"]:
                    print "Please respond with 'yes'/'no' (or 'y'/'n')."
                    sys.stdout.write("Terminate all running instances? [Y/n] ")
                    answer = raw_input().lower()
                if answer in ["n", "no"]:
                    self.instances = []
                    print 'Aborted.'
        if self.instances:
            # Create a list of instances' ids
            term = []
            for instance in self.instances:
                term.append(instance.id)
            # Terminate instances
            terminated = conn.terminate_instances(term)
            print "Successfully terminated instances: ",
            sys.stdout.write(terminated[0].id)
            for instance in terminated[1:]:
                sys.stdout.write(", " + instance.id)
            sys.stdout.write("\n")
            sys.stdout.flush()
            if len(term) != len(terminated):
                print "Failed to terminate all running instances. Please terminate them manually."
                print "Still running instances:"
                s = set(terminated)
                failed = [i for i in term if i not in s]
                for instance in failed:
                    print instance
            # Wait for all instances to completely shut-down
            for instance in self.instances:
                status = instance.update()
                while status == 'shutting-down':
                    time.sleep(2)
                    status = instance.update()
            try:
                # Delete created key and security group
                conn.delete_key_pair(self.key)
                conn.delete_security_group(self.security_group)
                os.remove(str('/tmp/' + self.key + '.pem'))
                print 'Removed keypair from disk'
            except:
                print "There are remaining keypairs and/or security groups. Make sure to delete"
                print "them if not needed."
        else:
            print "No running instances to terminate"
        conn.close()

if __name__ == "__main__":    
    instances = InstanceHandler()
    if len(sys.argv) == 2:
        if 'launch' == sys.argv[1]:
            instances.launch()
        elif 'terminate' == sys.argv[1]:
            instances.terminate()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s launch|terminate" % sys.argv[0]
        sys.exit(2)