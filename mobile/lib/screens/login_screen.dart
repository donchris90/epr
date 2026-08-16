import 'package:flutter/material.dart';
import 'package:dio/dio.dart';

import '../api/api_client.dart';
import '../theme/app_theme.dart';
import 'today_screen.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient apiClient;

  const LoginScreen({super.key, required this.apiClient});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  String? _errorMessage;

  Future<void> _submit() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await widget.apiClient.login(_emailController.text.trim(), _passwordController.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => TodayScreen(apiClient: widget.apiClient)),
      );
    } on DioException catch (e) {
      // A 401 here is "Invalid credentials" per the real backend
      // (backend/app/auth/routes.py) -- anything else (timeout, no
      // connectivity, 5xx) gets a distinct, honest message rather
      // than being folded into the same "wrong password" text, since
      // those call for a different next action from the user.
      setState(() {
        _errorMessage = e.response?.statusCode == 401
            ? 'Incorrect email or password.'
            : 'Could not reach the server. Check your connection and try again.';
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'SiteForge Field',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: SiteForgeColors.navy900),
                  ),
                  const SizedBox(height: 32),
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Password'),
                    onSubmitted: (_) => _isLoading ? null : _submit(),
                  ),
                  if (_errorMessage != null) ...[
                    const SizedBox(height: 12),
                    Text(_errorMessage!, style: const TextStyle(color: SiteForgeColors.brick)),
                  ],
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: _isLoading ? null : _submit,
                    child: _isLoading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Sign in'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
