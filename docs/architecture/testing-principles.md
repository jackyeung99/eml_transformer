# Testing Philosophy

Tests should verify observable behavior, remain independent, and make failures easy to diagnose.

## General Testing Procedure

For each component:

1. Identify its public responsibilities.
2. Test the expected successful behavior.
3. Test important edge cases.
4. Test expected failure behavior.
5. Isolate external dependencies.
6. Add integration tests for complete workflows.
7. Add regression tests when a real bug is discovered.

Use the Arrange–Act–Assert pattern:

```python
def test_returns_none_for_empty_response(source, fake_response):
    # Arrange
    fake_response.text = ""

    # Act
    result = source.fetch()

    # Assert
    assert result is None
```

## Types of Tests

- **Unit tests** verify one behavior in isolation.
- **Integration tests** verify that multiple components work together.
- **Workflow tests** verify a public entry point from input to output.
- **Regression tests** preserve examples that previously caused failures.

Prefer small synthetic inputs for isolated rules and representative real samples for regression and integration tests.

## Fixtures

Pytest fixtures provide reusable test setup:

```python
@pytest.fixture
def fake_storage():
    return FakeStorage()
```

Tests request fixtures through function parameters:

```python
def test_writes_records(fake_storage):
    ...
```

Pytest creates fixtures automatically. Fixtures are independent for each test by default, preventing state from leaking between tests.

Store fixtures in the lowest `conftest.py` directory shared by all tests that require them:

```text
tests/
├── conftest.py
├── ingestion/
│   ├── conftest.py
│   └── test_pipeline.py
└── embedding/
    ├── conftest.py
    └── test_pipeline.py
```

- `tests/conftest.py` provides fixtures to the entire test suite.
- `tests/ingestion/conftest.py` provides fixtures only to ingestion tests.
- `tests/embedding/conftest.py` provides fixtures only to embedding tests.

Do not import fixtures from `conftest.py`. Pytest discovers and injects them automatically.

## Helpers

Helpers are ordinary functions that reduce repeated test code:

```python
def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
```

Use helpers for stateless operations such as:

- Loading sample files
- Creating standard dictionaries
- Comparing structured outputs
- Constructing repeated test inputs

Place a helper directly in the test file when it is used only there. Move it to `helpers.py` when several test modules use it.

```text
tests/
├── conftest.py
├── helpers.py
├── test_parsing.py
└── test_pipeline.py
```

Use a fixture when setup, cleanup, state, or dependency management is required. Use a helper when a normal function is sufficient.

## Dependency Injection

Dependency injection means giving a component its dependencies instead of creating them inside the component.

Without dependency injection, the scraping pipeline constructs the real scraper internally:

```python
def _scrape_dataframe(
    self,
    df: pd.DataFrame,
    scraping_config: dict[str, Any],
) -> pd.DataFrame:
    scraper = HybridArticleScraper(
        ArticleScraperConfig(
            timeout=scraping_config["timeout"],
        )
    )
```

This tightly couples the pipeline to `HybridArticleScraper` and makes testing harder.

Instead, inject the scraper when constructing the pipeline:

```python
class ScrapingPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
        scraper: HybridArticleScraper,
    ):
        self.storage = storage
        self.paths = paths
        self.scraper = scraper
```

The pipeline then uses the injected scraper:

```python
def _scrape_dataframe(
    self,
    df: pd.DataFrame,
) -> pd.DataFrame:
    return self.scraper.scrape_dataframe(df)
```

Production code provides the real scraper:

```python
pipeline = ScrapingPipeline(
    storage=storage,
    paths=paths,
    scraper=HybridArticleScraper(config),
)
```

Tests provide a controlled fake:

```python
class FakeScraper:
    def scrape_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result["text"] = "Fake article text"
        result["scrape_status"] = "success"
        return result
```

```python
pipeline = ScrapingPipeline(
    storage=FakeStorage(),
    paths=FakeStoragePaths(),
    scraper=FakeScraper(),
)
```

This separates responsibilities:

- The pipeline manages records, storage, and workflow.
- The scraper manages HTTP requests and article extraction.

Benefits include:

- No real network requests in pipeline tests.
- Faster and predictable tests.
- Easy simulation of successes and failures.
- Less patching of internal implementation details.

## Fakes and Mocks

A fake is a small working replacement for a real dependency:

```python
class FakeStorage:
    def __init__(self):
        self.data = {}

    def write(self, key, value):
        self.data[key] = value
```

This injected fake storage is incredibly helpful for testing code that normally would write to the data folder such as the pipeline steps. Using this mock we can avoid writing fake data files and instead keep everything in memory.

Additionaly we can modify the mock method to records interactions and supports assertions about how it was called:

```python
session.get.assert_called_once_with(
    url,
    params=expected_params,
    timeout=15,
)
```

Use fakes when simple realistic behavior improves readability. Use mocks when the main goal is verifying calls or interactions.

## Test Organization

tests should resemble the src folder and can be brokend down by component or behavior:

```text
tests/
    ingestion/
        sources/ 
            iem_afos/
            ├── conftest.py
            ├── helpers.py
            ├── test_api.py
            ├── test_parsing.py
            ├── test_standardization.py
            └── test_pipeline.py
```

Test classes may organize related tests:

```python
class TestFetchRecords:
    def test_returns_records(self):
        ...

    def test_handles_empty_result(self):
        ...
```

Classes are optional and should only improve navigation. They should not create shared mutable state between tests.

Each test should:

- Verify one clearly named behavior.
- Run independently.
- Avoid real external services.
- Assert specific results.
- Fail for one understandable reason.