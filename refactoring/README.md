Hello Claude, you are my architect, I need you to help re-organize and re-architect into a pipeline.

Rockit project is a suite of modules to help with research strategies, perform back test, optimize for entry model such as entry, risk , reward.  It would build a portfolio of strategies and run rigorous back test over 259 sessions.  Most of the strategies are using Dalton Market auction theory, combine with some technical analysis including ICT liquidity, TPO, volume profile, BPR , FVG, etc.  Reports and implementation ideas are published.

Once the strategies are researched, we bring into Rockit-Framework where we attempt to translate this into python deterministic data.  From there, we have code to generate training data, annotate the data and bench mark.  THen we manually run the training on spark dgx with Lora.

Separately, we take the resarch and generate ninja trader indicators and even execution strategies.  And sometime this doesn't match up with Ninja performance vs. back test.

So are you can see the research looks good, but it is translated into implementations.

As I iterate from research to implementation, it is taking too much churn.  Any tweak update from reearch, we have to go through the whole code update in separate repos.

I think we need to have the researcher built on a framework that supports back testing and generating deterministic data, that can be easily re-used as libraries for LLM training and LLM inference.  We use the same inference code to feed deterministic data that it hasn't seen to generate inference and trade ideas.

Then we have a UI dashboard to display the information based on deterministic output and llm output.

So far the most painful aspect is having to translate python code into ninja code and churn  / maintain it.

So I am thinking this common code base from research, should be able to be containerize and publish the information via an end point like gcp cloud run.  

Any client can take the information and draw indicators such as trading view and ninja trader.  So we then just need an indicator for each platform to call API to draw boxes and lines (annotation language).  This reduces client code dependency.

The same API can generate trade  setups, and we can have a strategy in ninja trader to execute entry, stop and manage /trail target.

We need to think of a way to do this so it's part of our pipeline.  In my job interview, there were discussion using different ml ops tools to audomate training instead of running things manually.

Here are the repositories to inspect

Research branch
https://github.com/LePhanFF/BookMapOrderFlowStudies/tree/claude/research-evaluation-strategies-QcnQK

ninjatrader indicator
https://github.com/LePhanFF/BookMapOrderFlowStudies/tree/feature/next-improvements

LLm training and deterministic data generation
https://github.com/LePhanFF/rockit-framework/tree/claude-code-inference-simplification

Interview Prep
https://github.com/LePhanFF/InterviewPrep/tree/main/3_technical_deep_dives/data_pipelines


GCP Hosted API
https://github.com/LePhanFF/RockitAPI

GCP hosted UI
https://github.com/LePhanFF/LePhanFF-RockitUI

So your goal is to give me a proposal of architecture of new repository, new automation, new process that will make this project work and maintainable.  Propose and put architecture thoughts under architecture folder

