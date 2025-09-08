# Contributing to Bluetooth Sync

Thank you for your interest in contributing to Bluetooth Sync! This project aims to solve the common dual-boot Bluetooth pairing problem for Linux users.

## How to Contribute

### Reporting Issues
- Use the GitHub issue tracker to report bugs
- Include system information (Linux distro, Python version, hardware)
- Provide detailed steps to reproduce the issue
- Include relevant log files from the utility

### Feature Requests
- Check existing issues before creating new feature requests
- Explain the use case and expected behavior
- Consider backward compatibility

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Test your changes**: Run the test suite and validate on real hardware
4. **Follow code style**: Maintain consistent formatting and documentation
5. **Update documentation**: Ensure README reflects any changes
6. **Submit a pull request**: Include clear description of changes

### Testing
- Test on real dual-boot systems when possible
- Validate both successful and error scenarios
- Check compatibility with different Windows/Linux versions
- Run the installation validator: `python3 test_installation.py`

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints where appropriate
- Include docstrings for functions and classes
- Maintain comprehensive logging

## Development Setup

1. Clone the repository
2. Set up development environment:
   ```bash
   pipenv install
   pipenv shell
   ```
3. Make your changes
4. Test thoroughly before submitting

## Areas for Contribution

- **Hardware compatibility**: Test on different systems and storage types
- **Error handling**: Improve edge case handling
- **Documentation**: Improve setup instructions and troubleshooting
- **Registry parsing**: Support for newer Windows versions
- **GUI interface**: Add graphical user interface option
- **Automated testing**: Improve test coverage and automation

## Questions?

Feel free to open an issue for questions about contributing or the project architecture.

---

By contributing, you agree that your contributions will be licensed under the MIT License.
