import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MenuItem } from 'primeng/api';
import { AppMenuitem } from './app.menuitem';
import { AuthService } from '../../auth/auth.service';

@Component({
    selector: 'app-menu',
    standalone: true,
    imports: [CommonModule, AppMenuitem, RouterModule],
    template: `<ul class="layout-menu">
        <ng-container *ngFor="let item of model(); let i = index">
            <li app-menuitem *ngIf="!item.separator" [item]="item" [index]="i" [root]="true"></li>
            <li *ngIf="item.separator" class="menu-separator"></li>
        </ng-container>
    </ul> `
})
export class AppMenu {
    private readonly auth = inject(AuthService);

    readonly model = computed<MenuItem[]>(() => {
        if (this.auth.isAdmin()) {
            return [
                {
                    label: 'Navegacion',
                    items: [
                        { label: 'Reportar E-14', icon: 'pi pi-fw pi-file-edit', routerLink: ['/e14'] },
                        { label: 'Seguimiento Mesas', icon: 'pi pi-fw pi-chart-bar', routerLink: ['/tracking'] },
                        { label: 'Exportar TXT', icon: 'pi pi-fw pi-download', routerLink: ['/exportar'] }
                    ]
                }
            ];
        }

        if (this.auth.isTestigo()) {
            return [
                {
                    label: 'Navegacion',
                    items: [{ label: 'Reportar E-14', icon: 'pi pi-fw pi-file-edit', routerLink: ['/e14'] }]
                }
            ];
        }

        return [
            {
                label: 'Navegacion',
                items: []
            }
        ];
    });
}
