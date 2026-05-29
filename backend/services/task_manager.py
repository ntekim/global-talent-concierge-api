import asyncio


class TaskManager:
    def __init__(self, max_concurrent: int):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, asyncio.Task] = {}

    async def run(self, case_id: str, coro):
        async with self._sem:
            task = asyncio.create_task(coro, name=f"case-{case_id}")
            self._tasks[case_id] = task
            try:
                await task
            finally:
                self._tasks.pop(case_id, None)

    async def cancel(self, case_id: str):
        task = self._tasks.get(case_id)
        if task and not task.done():
            task.cancel()

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    async def cancel_all(self):
        for case_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()


task_manager = TaskManager(max_concurrent=10)
