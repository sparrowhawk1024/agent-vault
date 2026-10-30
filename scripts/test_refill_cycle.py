import urllib.request, json

req_reset = urllib.request.Request('http://127.0.0.1:8000/refill/reset', data=json.dumps({'initialAllowance': 5000}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req_reset) as r:
    print('Reset to 5,000 units:', json.loads(r.read()))

req_consume = urllib.request.Request('http://127.0.0.1:8000/refill/consume', data=json.dumps({'units': 4400, 'reason': 'Simulate peak inference'}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req_consume) as r:
    print('Consumed 4,400 units:', json.loads(r.read()))

req_stat = urllib.request.Request('http://127.0.0.1:8000/refill/status')
with urllib.request.urlopen(req_stat) as r:
    stat = json.loads(r.read())
    print(f"Before refill: {stat['remainingUnits']} / {stat['totalAllowance']} ({stat['percentageRemaining']}%) | isLowBalance={stat['isLowBalance']}")

req_pay = urllib.request.Request('http://127.0.0.1:8000/x402/client/pay', data=json.dumps({'packageId': 'pack-tf-2k'}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req_pay) as r:
    pay_res = json.loads(r.read())
    print(f"Payment executed! Success={pay_res['success']}, Units granted=+{pay_res['creditRecord']['unitsGranted']}")

with urllib.request.urlopen(req_stat) as r:
    stat2 = json.loads(r.read())
    print(f"After refill: {stat2['remainingUnits']} / {stat2['totalAllowance']} ({stat2['percentageRemaining']}%) | isLowBalance={stat2['isLowBalance']}")
