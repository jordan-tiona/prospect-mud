<!--
How give_directions works, for every NPC that has it. Engine mechanics in prompt form (Dev lane, like content/npc-shared-rules.md): world/prompt_builder.py adds this file only to the prompts of NPCs whose `actions` list give_directions. Which places an NPC knows, and anything in their own voice, stays in their persona's `## Actions` bullet. Check docs/npc-action-prompt-guidelines.md (#1, #9, #23, #27) before changing it.
-->

- Only call it when someone has actually asked the way somewhere - "how do I get to the workshop?", "which way is the café?", "where's the square from here?" Naming who knows about something isn't giving directions: telling someone a topic is another person's is a name, not a route, so don't call this unless they then ask how to get there.
- Call it the moment you've agreed to tell someone the way, with `destination` set to the place by name. Don't describe a route in words or in an *action* first, and don't give a holding reply like offering to help or saying you'll think about it - the route doesn't exist until it comes back to you.
- The route always starts from where the person is standing right now. If they ask the way from somewhere else, you can't answer that - say so plainly rather than guessing or calling this anyway.
- When you react to the result, state the exact turns and the places it names, in order, in your own words. Don't add any other place, street, landmark, stairs, shortcut, or detour the result didn't mention.
- If the result says there's no path, believe it over any assumption of your own, and say so plainly rather than guessing at a route.
- If they ask about a place you don't know, say so in words instead of calling this.
