I want to refactor, you know the source code so basically you have some background. 
Move src to srcv1 and tests to testsv1. 

I want to structure the code by the platform ex: gemfire, tibco, etc and external (colls already exist, no need to collect, basically normalize it to our models)

The reason being these platforms collectors will be so diff it makes no sense to maintain one single collector. 

Basically the conf dir exists inside these above folders, gemfire has its own etc. 

Everyone is diff and we bring them together, does that make sense to you? I want to start slow - gemfire first, we build end to end. 

The metric sample model is good however I am not sure if every platform fits that, I want to have a primary key and then have a generic metadata covering diff platforms. gemfire will have clusters (cache, locator) and apigee does not. external coll like avi lb has service engines, virtual machines etc. 

Also I want to make a bigger change in alerting - we should have a yaml file to enable or disable a platform all together and also there should be switch like threshold: true or false and policies: true or false, meaning alert me on thresholds anomalies or / and alert me also on policies (user defined) - policies are mathematical relationships of metrics. If both false no alerts. 

With this new refactoring I want to have a clear path to understanding the maintenance windows. I know the current code also caters for us holidays I want to keep that too. Every platform should define its cob scenarios, how to query the status at the data center levels. Mechanism to integrate this in to this framework as a whole.

I like the current cli commands

And with the new yaml under each platform should be able to ignore the whole platform altogether if I run the daemon and also I can control the individual targets inside collection

The main reason for refactoring is every platform is diff and we are trying to FIT or STITCH together. 

I want to discuss this in deep before we begin. Ask me questions. 