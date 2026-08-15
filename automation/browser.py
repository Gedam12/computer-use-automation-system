from playwright.async_api import Page

from automation.models import Locator, LocatorStrategy


class BrowserSurface:
    def __init__(self, page: Page):
        self.page = page

    def resolve_locator(self, locator: Locator):
        if locator.strategy == LocatorStrategy.ROLE:
            return self.page.get_by_role("button", name=locator.value)

        if locator.strategy == LocatorStrategy.LABEL:
            return self.page.locator(f'[name="{locator.value}"]')

        if locator.strategy == LocatorStrategy.TEXT:
            return self.page.get_by_text(locator.value, exact=True)

        if locator.strategy == LocatorStrategy.CSS:
            return self.page.locator(locator.value)

        raise ValueError(f"Unsupported locator strategy: {locator.strategy}")

    async def type_text(self, locator: Locator, value: str):
        element = self.resolve_locator(locator)
        await element.fill(value)

    async def click(self, locator: Locator):
        element = self.resolve_locator(locator)
        await element.click()

    async def read_text(self, locator: Locator) -> str:
        element = self.resolve_locator(locator)
        text = await element.inner_text()
        return text.strip()

    async def is_visible(self, locator: Locator) -> bool:
        element = self.resolve_locator(locator)
        return await element.is_visible()