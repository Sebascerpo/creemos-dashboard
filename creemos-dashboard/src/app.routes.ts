import { Routes } from '@angular/router';
import { AppLayout } from './app/layout/component/app.layout';
import { authGuard } from './app/auth/auth.guard';
import { emailAccessGuard } from './app/auth/email-access.guard';
import { ADMIN_EMAIL, TESTIGO_EMAIL } from './app/auth/auth.service';

export const appRoutes: Routes = [
    {
        path: 'auth',
        loadChildren: () => import('./app/auth/auth.routes')
    },
    {
        path: '',
        component: AppLayout,
        canActivate: [authGuard],
        children: [
            { path: '', redirectTo: 'e14', pathMatch: 'full' },
            {
                path: 'e14',
                canActivate: [emailAccessGuard],
                data: { allowedEmails: [ADMIN_EMAIL, TESTIGO_EMAIL] },
                loadComponent: () => import('./app/e14/e14-form/e14-form.component').then((m) => m.E14FormComponent)
            },
            {
                path: 'tracking',
                canActivate: [emailAccessGuard],
                data: { allowedEmails: [ADMIN_EMAIL] },
                loadComponent: () => import('./app/tracking/tracking.component').then((m) => m.TrackingComponent)
            },
            {
                path: 'exportar',
                canActivate: [emailAccessGuard],
                data: { allowedEmails: [ADMIN_EMAIL] },
                loadComponent: () => import('./app/exportar/exportar-txt.component').then((m) => m.ExportarTxtComponent)
            },
            {
                path: 'perfil',
                canActivate: [emailAccessGuard],
                data: { allowedEmails: [ADMIN_EMAIL, TESTIGO_EMAIL] },
                loadComponent: () => import('./app/auth/profile').then((m) => m.ProfilePage)
            },
            { path: '**', redirectTo: '' }
        ]
    },
    { path: '**', redirectTo: '/auth/login' }
];
