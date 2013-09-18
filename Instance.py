'''
Created on Sep 9, 2013

@author: eviek.
'''
#!/usr/bin/env python

import boto.ec2, boto.ec2.cloudwatch
import sys, os, time, datetime, thread
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
        self.alarm = []
        self.initial_charges = 0
        self.charges_limit = 0
    
    def authenticate(self):
        print 'Checking if user has access rights..'
        db = MySQLdb.connect(host="localhost", user="root", passwd="evie", db="aws_users")
        cur = db.cursor() 
        cur.execute("select * from aws_auth where user='evie'")
        result = cur.fetch_all()
        if result:
            for row in result:
                print row
            print 'Authentication succeded. Access granted.'
            self.charges_limit = 0 #<---- to be fixed
        else:
            print 'Authentication failed. Please contact owner company to obtain access rights.'
            sys.exit(2)
    
    def launch(self):
        print "Perform configurations in AWS EC2 and request spot instances.."
        conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                          aws_secret_access_key=self.aws_secret_access_key)
        # Create private key and save to disk
#        keypair = conn.create_key_pair(self.key)
#        keypair.save("/tmp")
        # Create simple security group to allow ssh connections
#        self.group = conn.create_security_group(name=self.security_group, description=self.security_group)
#        self.group.authorize('tcp', 22, 22, '0.0.0.0/0')
        # Launch instances
#        start = datetime.datetime.now().isoformat()
#        end = (datetime.datetime.now() + datetime.timedelta(minutes=5)).isoformat()
        requests = conn.request_spot_instances('0.008', self.image, count=self.count, type='one-time',
                                              #valid_from=start, valid_until=end, launch_group='group_devil',
                                              key_name=self.key, security_groups=[self.security_group],
                                              #user_data=????,
                                              instance_type=self.instance_type)
                                              #placement=self.availabity_zone)
        fulfilled = 0
        while fulfilled == 0:
            fulfilled = 1
            reqs = ""
            for request in requests:
                if str(conn.get_all_spot_instance_requests(request_ids=[str(request.id)])[0].status.code) != 'fulfilled':
                    reqs+=str(request.id)+' '
                    fulfilled = 0
            if reqs != "":
                print "waiting on requests: " + reqs
            else:
                print "Spot instances request fulfilled"
            time.sleep(10)
        for request in requests:
            iid = conn.get_all_spot_instance_requests(request_ids=[str(request.id)])[0].instance_id
            reservation = conn.get_all_instances(filters={'instance-id': iid})
            self.instances = self.instances + reservation[0].instances
        # Wait for all instances to be up and running
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
        if self.instances:
            print "Terminating instances.."
            conn = boto.ec2.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                              aws_secret_access_key=self.aws_secret_access_key)
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
            conn.close()
        else:
            print "No running instances to terminate"
        if self.alarm:
            self.alarm.delete()
            print 'Deleted alarm'
    
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
        if self.instances:
            instances = ''
            for instance in self.instances[0:len(self.instances)-1]:
                instances += str(instance.id) + ','
            instances += str(self.instances[len(self.instances)-1].id)
            conn = boto.ec2.cloudwatch.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                                         aws_secret_access_key=self.aws_secret_access_key)
            self.alarm = conn.describe_alarms(alarm_names=['charges_'+instances])[0]
            conn.close()
        return hosts, ips
    
    def get_billing(self):
        conn = boto.ec2.cloudwatch.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                                     aws_secret_access_key=self.aws_secret_access_key)
        #metrics = conn.list_metrics()
        #print metrics
        metrics = conn.list_metrics(metric_name='EstimatedCharges',namespace='AWS/Billing')
        end = datetime.datetime.now()
        start = end - datetime.timedelta(hours=8)
        print 'Service\t\t\tLatest update\t\tEstimated charges'
        for m in metrics[0:len(metrics)-1]:
            datapoints = m.query(start, end, 'Sum')
            if datapoints:
                last=len(datapoints)
                sys.stdout.write(m.dimensions['ServiceName'][0])
                sys.stdout.write('\t\t'+str(datapoints[0]['Timestamp']))
                sys.stdout.flush()
                print '\t' +str(datapoints[0]['Sum']) + ' '+ m.dimensions['Currency'][0]
        sys.stdout.write('Total charges:\t\t\t\t\t')
        sys.stdout.flush()
        datapoints = metrics[len(metrics)-1].query(start, end, 'Sum')
        print str(datapoints[0]['Sum']) + ' '+ m.dimensions['Currency'][0]
        self.initial_charges = float(datapoints[0]['Sum'])
        conn.close()
    
    def set_alarm(self):
        conn = boto.ec2.cloudwatch.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                                     aws_secret_access_key=self.aws_secret_access_key)
        instances = ''
        for instance in self.instances[0:len(self.instances)-1]:
            instances += str(instance.id) + ','
        instances += str(self.instances[len(self.instances)-1].id)
        self.alarm = boto.ec2.cloudwatch.MetricAlarm(name='charges_'+instances, metric='EstimatedCharges',
                                                     namespace='AWS/Billing', statistic='Sum', comparison='>',
                                                     threshold=float(self.initial_charges+self.charges_limit),
                                                     period=3600, evaluation_periods=6,
                                                     description="Alarm to terminate instances if charges exceed limit",
                                                     dimensions={"Currency":"USD"},
                                                     alarm_actions=['arn:aws:sns:us-east-1:460252822275:devel_charges'])
        conn.create_alarm(self.alarm)
        conn.close()
        print 'Created alarm to terminate instances if charge limit is exceeded'
        #thread.start_new_thread(self.monitor_alarm, ())
    
    def monitor_alarm(self):
        conn = boto.ec2.cloudwatch.connect_to_region(self.region, aws_access_key_id=self.aws_access_key_id,
                                                     aws_secret_access_key=self.aws_secret_access_key)
        metrics = conn.list_metrics(metric_name='EstimatedCharges',namespace='AWS/Billing')
        try:
            while True:
                end = datetime.datetime.now()
                start = end - datetime.timedelta(hours=8)
                datapoints = metrics[len(metrics)-1].query(start, end, 'Sum')
                if float(datapoints[0]['Sum']) > float(self.initial_charges+self.charges_limit):
                    print 'Charges limit reached, shutting-down everything!'
                    self.terminate_instances()
                    self.get_billing()
                    sys.exit(0)
                time.sleep(300)
        except (KeyboardInterrupt, SystemExit):
            conn.close()

if __name__ == "__main__":
    instances = InstanceHandler()
    if len(sys.argv) == 2:
        if 'launch' == sys.argv[1]:
            #instances.authenticate()
            instances.launch()
        elif 'auth' == sys.argv[1]:
            #instances.authenticate()
            print 'wait'
        elif 'get_billing' == sys.argv[1]:
            instances.get_billing()
        else:
            print "Unknown command"
            sys.exit(2)
    elif len(sys.argv) > 2:
        if 'terminate' == sys.argv[1]:
            instances.get_instances()
            instances.terminate()
        elif 'set_alarm' == sys.argv[1]:
            #instances.authenticate()
            instances.get_instances()
            instances.get_billing()
            instances.set_alarm()
        else:
            print "Unknown command"
            sys.exit(2)
    else:
        print "usage: %s launch|auth|get_billing|terminate instance1 instance2 ..|set alarm instance1 instance2 .." % sys.argv[0]
        sys.exit(2)
    sys.exit(0)
