platform linux -- Python 3.12.3, pytest-8.4.1, pluggy-1.6.0
rootdir: /home/ampchat/testing_demo
plugins: anyio-4.2.0, mock-3.14.1, cov-6.1.2, asyncio-0.21.0, aiosqlite-0.19.0
asyncio mode=Mode.STRICT, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 1 item

tests/test_my_app.py 
Patch is active. The real function will NOT be called.
Processing user data...
F

=================================== FAILURES ===================================
_____________________ test_process_user_data_with_patch ________________________

mocker = <pytest_mock.plugin.MockerFixture object at 0x7f2975eab530>

    def test_process_user_data_with_patch(mocker):
        """
        Tests the logic of process_user_data without calling the slow API.
        """
        # --- Arrange ---
        # 1. Use mocker.patch to find and replace the slow function.
        # The target string 'my_app.get_data_from_slow_api' tells patch:
        # "Go into the 'my_app' module and replace the 'get_data_from_slow_api' object."
        mocked_api_call = mocker.patch(
            'src.my_app.get_data_from_slow_api',
            return_value="MOCKED DATA FOR USER123"  # Tell our mock what to return
        )

        print("\nPatch is active. The real function will NOT be called.")

        # --- Act ---
        # 2. Call the function we are testing. When it tries to call
        #    get_data_from_slow_api, it will hit our mock instead.
        result = process_user_data("user123")

        # --- Assert ---
        # 3. Check that the logic of our main function worked correctly with the FAKE data.
>       assert result == "Processed: MOCKED DATA FOR USER123"
E       AssertionError: assert 'Processing failed: No data' == 'Processed: M...A FOR USER123'
E         - Processed: MOCKED DATA FOR USER123
E         + Processing failed: No data

tests/test_my_app.py:25: AssertionError
=========================== short test summary info ============================
FAILED tests/test_my_app.py::test_process_user_data_with_patch - AssertionError: assert 'Processing failed: No data' == 'Processed: M...A FOR USER123'
1 failed in 0.38s