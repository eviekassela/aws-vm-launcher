'''
Created on Aug 2, 2013

@author: eviek.
'''
#!/usr/bin/python2.6

import boto.ec2
import sys, time
from ConfigParser import ConfigParser

class InstanceHandler:
    
    def __init__(self):
        
        ## Reads the configuration properties
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
        self.conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id, 
                                               aws_secret_access_key=self.aws_secret_access_key)
    
    def launch(self):
        reservation = self.conn.run_instances(self.image, min_count=self.count, max_count=self.count, 
                                              key_name=self.key, security_groups=[self.security_group], 
                                              instance_type=self.instance_type)
        instances = reservation.instances
        for instance in instances:
            status = instance.update()
            while status == 'pending':
                time.sleep(2)
                status = instance.update()
        count = 0;
        print "Launched new instances:"
        print "Name\t\tInstance\tHostname"
        for instance in reservation.instances:
            count += 1
            name = self.hostname_template + str(count)
            instance.add_tag("Name", name)
            print name + "\t" + instance.id + "\t" + instance.public_dns_name
    
    def terminate(self):
        reservations = self.conn.get_all_instances(filters={'instance-state-name': 'running'})
        if reservations:
            # Get running instances from only 1 reservation
            instances = reservations[0].instances
            term = []
            for instance in instances:
                term.append(instance.id)
            terminated = self.conn.terminate_instances(term)
            print "Successfully terminated instances: ",
            sys.stdout.write(terminated.pop(0).id)
            for instance in terminated:
                sys.stdout.write(", " + instance.id)
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            print "No running instances to terminate"

if __name__ == "__main__":    
    instance = InstanceHandler()
    if len(sys.argv) == 2:
        if 'launch' == sys.argv[1]:
            instance.launch()
        elif 'terminate' == sys.argv[1]:
            instance.terminate()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s launch|terminate" % sys.argv[0]
        sys.exit(2)
