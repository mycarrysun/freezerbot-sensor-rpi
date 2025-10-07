# Project Guidelines

I am  software engineer working with the following technologies:
- backend and fronted using laravel 12, using livewire for the views, and a postgres database
- infrastructure is hosted in laravel cloud
- deployments managed with auto deploys via laravel cloud, and raspberry pi sensors with a python script installed before delivery that talks to the laravel api - the firmware updater updates the code on the raspberry pi nightly at 3am with the updates from the main branch on git

What the company does:
Freezerbot is an app that allows business owners to track their freezer temperatures and get alerted when things are out of temp. This is critical for things like biochemical labs and food service as lots of product can be lost when things become too warm.

How the app works:
The app works as a backend API, that stores information about all the freezers and each freezer has an attached sensor. The sensors are a raspberry pi zero-w that sends an update every minute to the server with the current temperature. The raspberry pi uses a simple Python script that hits the backend API via http calls. The raspberry pi is initially configured with wifi configurations and the user's credentials (which are used to retrieve an api token) for the backend API before being setup on location. 

We have a few conventions and principles I want you to know about:
- When writing python, make sure to always keep code in modules and import from modules in the repository rather than duplicating code
- When writing python, try to avoid try/catch unless its needed for executing more code. Do not use it to just print an exception to the terminal. When printing exceptions, always always!! use traceback.format_exc().
- When writing typescript, do not under any circumstance use the `any` type. Always prefer `unknown` instead. Use best practices and refer to strict mode documentation on how to avoid using `any`.
- repeat yourself as little as you can - if it makes sense, sometimes you can repeat yourself twice, but if you hit 3 times of duplicate code you should extract into a function
- instead of using comments to describe code, extract into variables and functions and classes that verbosely describe what is going on. Don't be afraid to use longer variable/method names to achieve this.
- when writing unit tests, prefer to break out test cases into groups of functionality. For the frontend this will result in more `describe` blocks. For the backend this will result in a method name in this structure `nameOfMethod_conditionOrSetup_expectedResultAfterRunningSubjectUnderTest`.

--
General guidelines for how you should respond:
- focus on accuracy and correctness over being made to feel heard or supported in a conversational manner
- do not use politically charged buzzwords, let's stick to apolitical terminology when describing things
- analyze the entire code/error message for full context. Do not forget to fully analyze the code you are given.
- Focus on practical real world solutions
- Tailor the responses to the typical conventions in the technologies in question. Only go outside the norm when it is a convention that we use in our specific codebase.
- Keep your answer as short as you can, but make sure to thoroughly explain each code block, make sure to never EVER leave comments in code that you're writing such as "fill in rest of function here"