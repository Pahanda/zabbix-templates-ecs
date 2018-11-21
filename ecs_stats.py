#!/usr/bin/env python
import datetime
import sys
from optparse import OptionParser
import boto3
import json

### Arguments
parser = OptionParser()
parser.add_option("-c", "--cluster-name", dest="cluster_name",
                help="ECS cluster name")
parser.add_option("-s", "--service-name", dest="service_name", default="",
                help="ECS service name")
parser.add_option("-a", "--access-key", dest="access_key", default="",
                help="AWS Access Key")
parser.add_option("-k", "--secret-key", dest="secret_key", default="",
                help="AWS Secret Access Key")
parser.add_option("-m", "--metric", dest="metric",
                help="ECS cloudwatch metric")
parser.add_option("-r", "--region", dest="region", default="us-east-1",
                help="ECS region")
parser.add_option("-d", "--discover",action="store_true", dest="discover", default=False,
		help="Discover services in a cluster (boolean)")

(options, args) = parser.parse_args()

if (options.cluster_name == None):
    parser.error("-c ECS cluster name is required")
if (options.metric == None) and (options.discover == False):
    parser.error("-m ECS cloudwatch metric is required")

if not options.access_key or not options.secret_key:
    use_roles = True
else:
    use_roles = False

metrics = {"CPUReservation":{"type":"float", "value":None},
    "CPUUtilization":{"type":"float", "value":None},
    "MemoryReservation":{"type":"float", "value":None},
    "MemoryUtilization":{"type":"float", "value":None}}
end = datetime.datetime.utcnow()
start = end - datetime.timedelta(minutes=5)

### Zabbix hack for supporting FQDN addresses
### This is useful if you have clusters with the same nam but in diffrent AWS locations (i.e. foo in eu-central-1 and foo in us-east-1)
if "." in options.cluster_name:
    options.cluster_name = options.cluster_name.split(".")[0]

if use_roles:
    conn = boto3.client('cloudwatch', region_name=options.region)
else:
    conn = boto3.client('cloudwatch', aws_access_key_id=options.access_key, aws_secret_access_key=options.secret_key, region_name=options.region)

if options.metric in metrics.keys() and not options.discover:
    k = options.metric
    vh = metrics[options.metric]

    try:
	dims = []
	dims.append({'Name': "ClusterName", 'Value': options.cluster_name})
	if options.service_name:
		dims.append({'Name': "ServiceName", 'Value': options.service_name})
        res = conn.get_metric_statistics(Namespace="AWS/ECS", MetricName=k, Dimensions=dims, StartTime=start, EndTime=end, Period=60, Statistics=["Average"])
    except Exception as e:
        print("status err Error running ecs_stats: %s" % e)
        sys.exit(1)
    datapoints = res.get('Datapoints')
    if len(datapoints) == 0:
        print("Could not find datapoints for specified cluster and service. Please review if provided cluster (%s), service (%s), and region (%s) are correct" % (options.cluster_name, options.service_name, options.region))

    average = datapoints[-1].get('Average') # last item in result set
    # if (k == "FreeStorageSpace" or k == "FreeableMemory"):
    #         average = average / 1024.0**3.0
    if vh["type"] == "float":
        metrics[k]["value"] = "%.4f" % average
    if vh["type"] == "int":
        metrics[k]["value"] = "%i" % average

    #print "metric %s %s %s" % (k, vh["type"], vh["value"])
    print("%s" % (vh["value"]))
elif options.discover:
    try:
        response = conn.list_metrics(Dimensions=[{'Name': "ClusterName", 'Value': options.cluster_name}],MetricName="CPUUtilization",Namespace="AWS/ECS")

	services = []

	for metric in response['Metrics']:
	    # Filter out the cluster total; we already know about that one.
	    if len(metric['Dimensions']) > 1:
		services.append({"{#SERVICE}": metric['Dimensions'][0]['Value']})

	raw = {"data": services}
	print json.dumps(raw)

    except Exception as e:
	print("status err Error running ecs_stats: %s" % e)
