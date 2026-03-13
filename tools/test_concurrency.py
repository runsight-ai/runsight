import asyncio
import httpx
import time


async def run_workflow(client: httpx.AsyncClient, index: int):
    # Testing the /api/workflows endpoint with a concurrent load
    try:
        response = await client.post(
            "http://localhost:8000/api/workflows/test_workflow/run",
            json={"id": f"task-{index}", "instruction": "Test task", "context": f"Context {index}"},
            timeout=10.0,
        )
        return {"index": index, "status": response.status_code}
    except Exception as e:
        return {"index": index, "error": str(e)}


async def main():
    start = time.time()
    async with httpx.AsyncClient() as client:
        # Launch 5 requests concurrently
        tasks = [run_workflow(client, i) for i in range(5)]
        results = await asyncio.gather(*tasks)

    for res in results:
        print(res)
    print(f"Finished 5 concurrent requests in {time.time() - start:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
