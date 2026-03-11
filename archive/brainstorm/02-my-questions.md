My questions are:

1. what are we storing in timeslice db?
2. we have 259+ sessions and growing, when we run generation of training data for 90 days, why can't we run for 259+ days, we have it benchmarked, why can't we use RAG ?
3. for CRI and Dalton Market profile, and orderflow - should we build some RAG ideas here
4. industry love to use agent + RAG, where can we apply this to our architecture
5. Architecture goals - can you verify the design for the following use cases

#1 - I can test new strategies with Claude, back test, tune
#2 - strategy framework should have a standard way to analyze market, conditions for setup, htf analysis,  order flow confirmation, entry model, target, stop
#3 - strategy framework should have measuruments
#4 - entry model for testing strategies

unicorn ict model
orderflow cvd model
smt divergnece model
liquidity sweep and reverse
TPO rejection model
3 drive to reverse
double top
trendline mnodel
backside of trendline
tick divergence
BPR
any others ?
#5 - stop model
 
 1 atr
 2 atr
 lvn/hvn
 ifvg
 any others?

 #6 - profit taking
 1 ATR
 2 ATR
 trailing to BE after 5 min fvg 
 trailing to BE after BPR inverted and cisd
 2R 
 3R
 4H gap fill
 1H gap fill
 time based liquidity
 any others ?

What we want is consistent code for these models (entry, stop, target) so it is consistently used during back testing, during playbook generation and during execution.

6. validate that I can re-purpose all back test - doing a PR , and the strategy is incorporated into the architecture with some yaml configuration - currently there is too much churn.  So goal is to reduce churn for strategy maintenance

7. we should have a database of backtested data for each strategy promoted, so agents later can use during consensus building.  We need to think about what will agent debate about using live vs historical data, useful information so agents can make meaningful discussions and confidence they are making the right decisions.  THen how we do bench mark those decisions for improvements later on.

8. any added strategy should use the consensus framework 
9. can we search the twitter and web to see if there are frameworks out there already , best practice for something like this, so we follow industry best practice, but need to build efficiently for what we have.
10.  the "brain" of the work should be done on nvdia dgx spark, if needed we reserve that for intelligence and off load to a PC to host agents (or run agents in GCP), and somehow expose our private vllm on the internet securely.
11. the rockitdashboard we can rebuild a new one, something to monitor the agents, what  they are thinking and the trades.  We are focused first as a decision support tool, but at some point ninja trader integration will do the indicator painting and place trades via api call to gcp for any signal.
12. The goal is to scale intelligence using more agents with one or more spark dgx, or spin up inference engines as needed with our training data.
13. identify any training LORA opportunity with one or more inference engine for these agents IF needed.  If not we are using Qwen 3.5 model 30b which seems solid with reasoning.
14. identify any else we are missing
15. fully validate our architecture first!
16. create a roadmap how to get started
17. on the self-learning - we need a way to run back test for example, i want to run Sept- November 2025 for a back test replay - record how it did and how it can improve itself.  Then i pick January 2026 to Feb 2026 - first witout the improvement back test, then with Sept-Nov 2025 improvements - A/B testing . would this work?  We need a mechanism to test the self learning mechanism.  
18. on evaluation - how do i know training my LLM has improved, make sure we have ways to mesure improvements across our architecture, this means we need to log sufficient metrics to measure improvements.  Need to make sure we benchmark performance of strategy, of agents , of orchestrator, of quality data generation, etc.
19. How do we setup claud to efficiently code up the roadmap - using multi agents to do most of the work .   I might have to use Qwen 3.5 to do most of the coding, but i need Opus 4.5 to do the heavy lifting architecture and design.
