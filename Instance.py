'''
Created on Sep 9, 2013

@author: eviek.
'''
#!/usr/bin/env python

import boto.ec2, boto.ec2.cloudwatch
#from boto.fps.connection import FPSConnection
import sys, os, time, datetime
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
        print "Perform configurations in AWS EC2 and launch instances.."
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        # Create private key and save to disk
#        keypair = conn.create_key_pair(self.key)
#        keypair.save("/tmp")
        # Create simple security group to allow ssh connections
#        self.group = conn.create_security_group(name=self.security_group, description=self.security_group)
#        self.group.authorize('tcp', 22, 22, '0.0.0.0/0')
        # Launch instances
#        reservation = conn.run_instances(self.image, min_count=self.count, max_count=self.count,
#                                         key_name=self.key, security_groups=[self.group], 
#                                         instance_type=self.instance_type, placement=self.availabity_zone)
        reservation = conn.run_instances(self.image, min_count=self.count, max_count=self.count,
                                         key_name=self.key, security_groups=[self.security_group], 
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
#        print 'Private key path: /tmp/' + self.key + '.pem'
        conn.close()
        # Return list of hostnames
        return hosts, ips
    
    def terminate(self):
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        if self.instances:
            print "Terminating instances.."
            # Create a list of instances' ids
            term = []
            for instance in self.instances:
                term.append(instance.id)
            # Terminate instances
            terminated = conn.terminate_instances(term)
            # Wait for all instances to completely shut-down
            for instance in terminated:
                status = instance.update()
                while status == 'shutting-down':
                    time.sleep(2)
                    status = instance.update()
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
#            try:
                # Delete created key and security group
#                conn.delete_key_pair(self.key)
#                conn.delete_security_group(self.security_group)
#                os.remove(str('/tmp/' + self.key + '.pem'))
#                print 'Removed keypair from disk'
#            except:
#                print "There are remaining keypairs and/or security groups. Make sure to delete"
#                print "them if not needed."
        else:
            print "No running instances to terminate"
        conn.close()
        
    def get_instances(self):
        hosts = []
        ips = []
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        for i in range(2, len(sys.argv)):
            res = conn.get_all_instances(filters={'instance-id': str(sys.argv[i])})
            if res:
                self.instances = self.instances + res[0].instances
                hosts.append(res[0].instances[0].public_dns_name)
                ips.append(res[0].instances[0].private_ip_address)
            else:
                print "Instance " + str(sys.argv[i]) + " does not exist"
                sys.stdout.write("Are you sure you want to continue? [Y/n] ")
                answer = raw_input().lower()
                while answer not in ["", "y", "ye", "yes", "n", "no"]:
                    print "Please respond with 'yes'/'no' (or 'y'/'n')."
                    sys.stdout.write("Are you sure you want to continue? [Y/n] ")
                    answer = raw_input().lower()
                if answer in ["n", "no"]:
                    self.instances = []
                    hosts = []
                    ips = []
                    print 'Aborted.'
                    break
        conn.close()
        return hosts, ips
    
    def get_billing(self):
#        fps_conn = FPSConnection(aws_access_key_id=self.aws_access_key_id,
#                                 aws_secret_access_key=self.aws_secret_access_key)
#        fps_conn.get_account_activity(StartDate='01-09-2013')
#        fps_conn.close()
        conn = boto.ec2.cloudwatch.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                                     aws_secret_access_key=self.aws_secret_access_key)
        #metrics = conn.list_metrics()
        #print metrics
        metrics = conn.list_metrics(metric_name=u'EstimatedCharges',namespace=u'AWS/Billing')
        end = datetime.datetime.now()
        start = end - datetime.timedelta(hours=12)
        print 'Service\t\t\tLatest update\t\tEstimated charges'
        for m in metrics[0:len(metrics)-1]:
            datapoints = m.query(start, end, 'Sum')
            if datapoints:
                sys.stdout.write(m.dimensions[u'ServiceName'][0])
                sys.stdout.write('\t\t'+str(datapoints[0][u'Timestamp']))
                sys.stdout.flush()
                print '\t' +str(datapoints[0][u'Sum']) + ' '+ m.dimensions[u'Currency'][0]
        metrics = conn.list_metrics(metric_name=u'NetworkIn',namespace=u'AWS/EC2')
        end = datetime.datetime.now()
        start = end - datetime.timedelta(hours=24)
        print 'AmazonEC2 total data transfered in:',
        data = 0
        for m in metrics[0:len(metrics)]:
            datapoints = m.query(start, end, 'Sum')
            if datapoints:
                data = data + datapoints[0][u'Sum']
        print str(data) + ' Bytes'
        conn.close()

if __name__ == "__main__":    
    instances = InstanceHandler()
    if len(sys.argv) == 2 and 'launch' == sys.argv[1]:
        instances.launch()
    elif len(sys.argv) == 2 and 'get_billing' == sys.argv[1]:
        instances.get_billing()
    elif len(sys.argv) > 2 and 'terminate' == sys.argv[1]:
        instances.get_instances()
        instances.terminate()
    elif 'terminate' != sys.argv[1] and 'launch' != sys.argv[1]:
        print "Unknown command"
        sys.exit(2)
    else:
        print "usage: %s launch|terminate instance1 instance2 .." % sys.argv[0]
        sys.exit(2)
    sys.exit(0)