# Grafo del agente de atención (LangGraph)

Versión del grafo: **1.1.0** · generado con `python manage.py agent_graph` (no editar a mano).

Fuente: `apps/ai/agent/graph.py`. Las líneas punteadas son aristas condicionales.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	load_context(load_context)
	classify_rules(classify_rules)
	classify_llm(classify_llm)
	validate_output(validate_output)
	decide_autonomy(decide_autonomy)
	check_auth(check_auth)
	respond_link_instructions(respond_link_instructions)
	call_tool(call_tool)
	respond(respond)
	respond_template(respond_template)
	create_ticket(create_ticket)
	route_ticket(route_ticket)
	respond_ticket(respond_ticket)
	request_review(request_review)
	human_review(human_review)
	apply_review(apply_review)
	__end__([<p>__end__</p>]):::last
	__start__ --> load_context;
	call_tool -.-> create_ticket;
	call_tool -.-> respond;
	call_tool -.-> respond_link_instructions;
	check_auth -.-> call_tool;
	check_auth -.-> respond_link_instructions;
	classify_llm --> validate_output;
	classify_rules -.-> classify_llm;
	classify_rules -.-> decide_autonomy;
	create_ticket --> route_ticket;
	decide_autonomy -.-> check_auth;
	decide_autonomy -.-> create_ticket;
	decide_autonomy -.-> respond_link_instructions;
	decide_autonomy -.-> respond_template;
	human_review --> apply_review;
	load_context --> classify_rules;
	request_review --> human_review;
	respond_ticket -.-> __end__;
	respond_ticket -.-> request_review;
	route_ticket --> respond_ticket;
	validate_output --> decide_autonomy;
	apply_review --> __end__;
	respond --> __end__;
	respond_link_instructions --> __end__;
	respond_template --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```
