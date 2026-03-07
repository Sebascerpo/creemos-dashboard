import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { PasswordModule } from 'primeng/password';
import { AuthService } from './auth.service';

@Component({
    selector: 'app-login',
    standalone: true,
    imports: [CommonModule, ButtonModule, InputTextModule, PasswordModule, FormsModule, MessageModule],
    templateUrl: './login.html',
    styleUrl: './login.scss'
})
export class Login {
    private readonly auth = inject(AuthService);
    private readonly router = inject(Router);

    email = '';
    password = '';
    loading = signal(false);
    error = signal('');

    ngOnInit(): void {
        if (this.auth.isAuthenticated()) {
            void this.router.navigateByUrl(this.auth.defaultRouteByRole());
        }
    }

    async onLogin(): Promise<void> {
        if (this.loading()) return;
        this.error.set('');
        if (!this.email.trim() || !this.password.trim()) {
            this.error.set('Debes ingresar email y password.');
            return;
        }

        this.loading.set(true);
        try {
            await this.auth.login(this.email, this.password);
            await this.router.navigateByUrl(this.auth.defaultRouteByRole());
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'No fue posible iniciar sesion.';
            this.error.set(msg);
        } finally {
            this.loading.set(false);
        }
    }
}
