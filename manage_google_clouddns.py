import re
import json
import argparse
import copy
from pprint import pprint
from collections import OrderedDict
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

# Need to provide a scope to only allow specific actions for our SA API key
scope = ['https://www.googleapis.com/auth/ndev.clouddns.readwrite']
# production service account API key
credentials = ServiceAccountCredentials.from_json_keyfile_name('serviceaccountcredential_json.key', scopes=scope)
service = discovery.build('dns', 'v1', credentials=credentials)
# production project and production zone file
project = 'ENTER_PROJECT_NAME'
managedZone = ''



# show all records or a specific one - this can print or return a dict of a specific record
def print_rr_record(recordset=None,returndict=None):
	resourceRecordSets = service.resourceRecordSets()
	request = resourceRecordSets.list(project=project, managedZone=managedZone)
	all_records_found = ''
	while request is not None:
		response = request.execute()

		# resource_record_set is a list of lists
		for resource_record_set in response['rrsets']:
			# rrdatas is the values
			# recordset set to None means we want to print all record sets
			if recordset is None:
				a_record_found =  resource_record_set['name'] + " of type " + resource_record_set['type'] + " and values:\n"
				values_found = ''
				for value in resource_record_set['rrdatas']:
					values_found = values_found + '\t' + value + '\n'

				all_records_found = all_records_found + a_record_found + values_found

			# if recordset is not None we want to print something specific
			else:
				for record in recordset:
					if re.match(record,resource_record_set['name']) or re.match(record + ".", resource_record_set['name']):
						a_record_found =  resource_record_set['name'] + " of type " + resource_record_set['type'] + " and values:\n"
						values_found = ''
						# This is just to print found record to screen
						if returndict is None:
							for value in resource_record_set['rrdatas']:
								values_found = values_found + '\t' + value + '\n'

							all_records_found = all_records_found + a_record_found + values_found
						# This does not print found record, but instead returns the recordset - used in updates
						else:
							return resource_record_set

		request = resourceRecordSets.list_next(previous_request=request, previous_response=response)

	if all_records_found:
		print all_records_found[:-1]
	else:
		print "No existing records found"


# To add/remove specific values from a resource record
def update_rr_record(name, action, values):

	# First you need to find if the record exists, if it doesn't then we'll just exit, if it does store it into
	# a variable as we need the exact ResourceRecord set in order to do a remove (there is no update, just delete and re-add in one transaction)
	change_body = { 'kind' : 'dns#change' }
	record_old = print_rr_record([name], 'true')

	# CNAME's record can only exist once and you can not remove the FQDN value of the CNAME. Instead you must remove the entire record.
	# Ex. 'cname.cryptik.org CNAME to cryptik.org'
	# cname.cryptik.org can't have two CNAME values. And you cant remove the existing cryptik.org value. Instead you delete the entire 'test.cryptik.org' record
	if not re.match('\.$', name):
		name = name + '.'

	if record_old['type'] == 'CNAME':
		print "Record set already exist and can't be a CNAME to multiple FQDNs nor can you remove what it is a CNAME to without removing the entire record set instead:\n"
		print_rr_record([name])
		return

	# Make a copy of the old record so we can do some work on the copy
	record_new = copy.deepcopy(record_old)

	if type(record_old) is dict:
		if 'add' == action:
			for value in values:
				if value in record_old['rrdatas']:
					print value + " already exists in " + name
				else:
					record_new['rrdatas'].append(value)
		elif 'remove' == action:
			for value in values:
				if value in record_old['rrdatas']:
					if len(record_new['rrdatas']) == 1:
						print "Removing " + value + " would cause the record to be empty. You should use the deleterecord option if this is what you want to do."
						return 
					record_new['rrdatas'].remove(value)
				else:
					print value + " does not exist in " + name

		change_body['additions'] = [ record_new ]
		change_body['deletions'] = [ record_old ]

 		if change_body['additions'] == change_body['deletions']:
			print "Resulting records are identical, no changes needed."
		else:
			request = service.changes().create(project=project, managedZone=managedZone, body=change_body)
			response = request.execute()
			pprint(response)
					
	else:
		print "Unable to find record set " + name

# Create a new resource record
def create_rr_record(name, recordtype, values, ttl):
 
	record_exists = print_rr_record([name], 'true')

	if type(record_exists) == dict and record_exists:
		print "Resource record " + name + " already exists with values shown below.\nIf you wish to modify the existing record then use 'updaterecord' instead of 'createrecord':\n"
		print_rr_record([name])
	else:
		print "\nCreating your resource record.."
		name = unicode(name)
		new_values = []
		for value in values:
			if recordtype == 'CNAME' and not re.match('\.$', value):
				value = value + '.'
				new_values.append(unicode(value))
			else:
				new_values.append(unicode(value))

		recordtype = unicode(recordtype)
		ttl = unicode(ttl)
		change_body = { 'kind' : 'dns#change' }
		record_new = { u'rrdatas' : new_values, u'kind' : u'dns#resourceRecordSet', u'type' : recordtype, u'name' : name, u'ttl' : ttl }
		change_body['additions'] = [ record_new ]
		request = service.changes().create(project=project, managedZone=managedZone, body=change_body)
		response = request.execute()
		pprint(response)

# Delete a r resource record
def delete_rr_record(name, record_type):
	record_found = print_rr_record(name, 'true')

	if record_found:

		# We found a record with the name we're looking for,	
		if record_found['type'] == record_type:
			print "Found the following record:\n"
			print_rr_record(name) 

			print "\nIMPORTANT!!!!!"
			answer = raw_input("Are you SURE to DELETE this RECORD? (yes/NO) ")
			if answer == "yes":
				print "Deleting record..."
				change_body = { 'kind' : 'dns#change' }
				change_body['deletions'] = [ record_found ]
				request = service.changes().create(project=project, managedZone=managedZone, body=change_body)
				response = request.execute()
				pprint(response)
			else:
				print "Not deleting record."
		else:
			print "Could not find a record with name: " + record_found['name'] + " and type: " + record_type


def parse_args():
	parser = argparse.ArgumentParser(description='Updates/Prints production Google DNS Records')

	subparsers = parser.add_subparsers(help='sub-command help', dest='subparser_name')

	parser_print = subparsers.add_parser('printrecords', help='Print all or specific records')
	parser_print.add_argument('-zone', dest='zone', required=True, help='ManagedZone name as displayed in Google CloudDNS. Ex. cryptik')
	parser_print.add_argument('-name', nargs='*', dest='names', required=False, help='Print specific records. Ex. test1.cryptik.org test2.cryptik.org') 

	parser_update = subparsers.add_parser('updaterecord', help='Update an existing record')
	parser_update.add_argument('-zone', dest='zone', required=True, help='ManagedZone name as displayed in Google CloudDNS. Ex. eyezone, ermisvc, eyedemand')
	parser_update.add_argument('-action',  dest='action', required=True, help='Action can be "remove" or "add"')
	parser_update.add_argument('-name',  dest='name', required=True, help='Name of record to be updated')
	parser_update.add_argument('-values', nargs='*', dest='values', required=True, help='Data to be added or removed from record set. Ex. 22.11.33.22 44.12.34.22')

	parser_create = subparsers.add_parser('createrecord', help='Create A record or CNAME record to be added to zone file')
	parser_create.add_argument('-zone', dest='zone', required=True, help='ManagedZone name as displayed in Google CloudDNS. Ex. cryptik')
	parser_create.add_argument('-name',  dest='name', required=True, help='Name of your record, e.g. test1.cryptik.org')
	parser_create.add_argument('-recordtype', dest='recordtype', required=True, help='Type of record being added. Limiting this to either "A" or "CNAME" for our script')
	parser_create.add_argument('-values', nargs='*', dest='values', required=True, help='A space-separated list of ips (A record) or hostnames (CNAME), e.g. 192.168.0.1 or test1.cryptik.org')
	parser_create.add_argument('-ttl', dest='ttl', required=True, help='TTL to be used for this record. Default is 300s (5 min)')

	parser_delete = subparsers.add_parser('deleterecord', help='Delete A records or CNAME records')
	parser_delete.add_argument('-zone', dest='zone', required=True, help='ManagedZone name as displayed in Google CloudDNS. Ex. cryptik')
	parser_delete.add_argument('-name', nargs=1, dest='name', required=True, help='Name of records to be deleted. Ex. arecord.cryptik.org brecord.cryptik.org')
	parser_delete.add_argument('-recordtype', dest='recordtype', required=True, help='Type of record being deleted. Limiting this to either "A" or "CNAME" for our script')

	args = parser.parse_args()
	return args

if __name__ == '__main__':
	args = parse_args()

	managedZone = args.zone

	if args.subparser_name == 'printrecords':
		print_rr_record(args.names)

	elif args.subparser_name == 'updaterecord':

		if args.action != "add" and args.action != "remove":
			print "Action must be 'add' or 'remove'"
		else:
			update_rr_record(args.name, args.action, args.values)

	elif args.subparser_name == 'createrecord':
		if args.recordtype != 'A' and args.recordtype != 'CNAME':
			print "Invalid record type.. can only be 'A' or 'CNAME'"
		else:
			create_rr_record(args.name, args.recordtype, args.values, args.ttl)

	elif args.subparser_name == 'deleterecord':
		if args.recordtype != 'A' and args.recordtype != 'CNAME':
			print "Invalid record type.. can only be 'A' or 'CNAME'"
		else:
			delete_rr_record(args.name, args.recordtype)
