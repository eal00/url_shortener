import random
import string

from locust import HttpUser, constant, task


class UrlShortenerUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        """
        Создаем 1000 ссылок в on_start, в т.ч. т.к. они потребуются для дальнейших заданий
        """
        self.created_links = []
        for _ in range(1000):
            original_url = f"https://example.com/test-{''.join(random.choices(string.ascii_lowercase, k=10))}"
            response = self.client.post("/links/shorten", json={"original_url": original_url})
            if response.status_code == 200:
                self.created_links.append(response.json()["short_code"])

    @task
    def redirect_url(self):
        if not self.created_links:
            return

        # Возьмем первую ссылку для тестирования. Чтобы не было много кеш-промахов
        popular_links_count = 1
        short_code = random.choice(self.created_links[:popular_links_count])
        self.client.get(f"/{short_code}", name="/[short_code]", allow_redirects=False)
