from typing import List

from artifactsmmo.service.tasks import Task


def gather_and_craft_recipe(
    quantity: int = 1,
    force_gather: bool = False,
    allow_fewer: bool = False,
    item: str = None,
    items: List[str] = None,
    leader: str = None,
    target: str = 'bank',
    global_max: int = None,
    request_support: bool = False,
    recipe_id: str = None,
) -> List[Task]:
    items = [] if items is None else items
    items.append(item) if item else None
    tasks = []
    for item in items:
        recipe_id = recipe_id or Task.generate_task_id()
        tasks.append(
            Task.gather_recipe(
                task_id=recipe_id,
                item=item,
                quantity=quantity,
                force_gather=force_gather,
                global_max=global_max,
                leader=leader,
                request_support=request_support,
            )
        )
        tasks.append(
            Task.craft_recipe(
                task_id=recipe_id,
                item=item,
                quantity=quantity,
                allow_fewer=allow_fewer,
                global_max=global_max,
                target=target,
                leader=leader,
            )
        )

    return tasks
