import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { PasswordModule } from 'primeng/password';
import { AuthService } from './auth.service';

@Component({
    selector: 'app-login',
    standalone: true,
    imports: [CommonModule, ButtonModule, InputTextModule, PasswordModule, FormsModule, RouterModule, MessageModule],
    styles: [
        `
            .login-shell {
                min-height: 100vh;
                background:
                    radial-gradient(circle at 15% 20%, rgba(5, 150, 105, 0.12), transparent 35%),
                    radial-gradient(circle at 85% 80%, rgba(2, 132, 199, 0.12), transparent 40%),
                    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
            }

            .login-card {
                backdrop-filter: blur(4px);
                box-shadow:
                    0 20px 50px rgba(15, 23, 42, 0.08),
                    0 1px 0 rgba(255, 255, 255, 0.75) inset;
            }
        `
    ],
    template: `
        <div class="login-shell flex items-center justify-center px-4 py-8">
            <div class="w-full max-w-md rounded-3xl border border-white/80 bg-white/90 p-6 login-card sm:p-8">
                <div class="mb-7">
                    <div class="mb-4 flex items-center justify-center">
                        <div class="rounded-2xl border border-surface-200 bg-white px-4 py-3 shadow-sm">
                            <img src="assets/CreemosColombiaRec_320.png" alt="Creemos" width="320" height="106" class="h-9 w-auto" />
                        </div>
                    </div>
                    <h1 class="px-2 text-center text-xl font-semibold leading-tight tracking-tight text-surface-900 sm:text-2xl">Acceso Plataforma E-14</h1>
                    <p class="mt-2 text-center text-sm text-surface-600">Inicia sesión para registrar y monitorear mesas.</p>
                </div>

                <div class="space-y-5">
                    <div class="space-y-2">
                        <label for="email" class="block text-sm font-medium text-surface-800">Email</label>
                        <span class="p-input-icon-left block">
                            <i class="pi pi-envelope"></i>
                            <input pInputText id="email" type="email" class="w-full" placeholder="usuario@correo.com" [(ngModel)]="email" />
                        </span>
                    </div>

                    <div class="space-y-2">
                        <label for="password" class="block text-sm font-medium text-surface-800">Password</label>
                        <p-password id="password" [(ngModel)]="password" [toggleMask]="true" [feedback]="false" [fluid]="true" />
                    </div>

                    <p-message *ngIf="error()" severity="error" [text]="error()" />

                    <button
                        pButton
                        type="button"
                        class="w-full"
                        [label]="loading() ? 'Ingresando...' : 'Ingresar'"
                        [disabled]="loading()"
                        (click)="onLogin()"
                    ></button>
                </div>
            </div>
        </div>
    `
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
