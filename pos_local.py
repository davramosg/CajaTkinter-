import sqlite3
import datetime
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

# Puerto o nombre de la impresora física en Windows (ej: "COM1", "LPT1" o el nombre compartido)
DESTINO_IMPRESORA = "COM1" 

class DatabaseManager:
    def __init__(self, db_name="caja_local.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_categoria TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                id_categoria INTEGER,
                precio REAL NOT NULL,
                FOREIGN KEY (id_categoria) REFERENCES categorias(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                total REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                cerrado INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detalle_ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_venta INTEGER,
                id_producto INTEGER,
                cantidad INTEGER,
                precio_unitario REAL,
                FOREIGN KEY (id_venta) REFERENCES ventas(id) ON DELETE CASCADE,
                FOREIGN KEY (id_producto) REFERENCES productos(id)
            )
        """)
        self.conn.commit()

    def query(self, sql, params=()):
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        self.conn.commit()
        return cursor

    def close(self):
        self.conn.close()


class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema POS Ultraligero - Local")
        self.root.geometry("1024x720")
        
        self.db = DatabaseManager()
        self.cart = [] 

        self.create_widgets()
        self.load_categories()
        
        self.root.bind('<F6>', lambda event: self.pedir_metodo_pago())

    def create_widgets(self):
        main_paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo para la grilla de productos (weight=4)
        left_frame = ttk.Frame(main_paned, padding=5)
        main_paned.add(left_frame, weight=4)

        self.notebook_categorias = ttk.Notebook(left_frame)
        self.notebook_categorias.pack(fill=tk.BOTH, expand=True, pady=5)

        # Panel derecho para el ticket actual (weight=1)
        right_frame = ttk.Frame(main_paned, padding=5)
        main_paned.add(right_frame, weight=1)

        lbl_ticket = ttk.Label(right_frame, text="TICKET ACTUAL", font=("Arial", 11, "bold"))
        lbl_ticket.pack(pady=5)

        self.cart_tree = ttk.Treeview(right_frame, columns=("Cant", "Producto", "Subtotal"), show="headings", height=18)
        self.cart_tree.heading("Cant", text="Cant")
        self.cart_tree.heading("Producto", text="Producto")
        self.cart_tree.heading("Subtotal", text="Subtotal")
        self.cart_tree.column("Cant", width=35, anchor="center")
        self.cart_tree.column("Producto", width=110)
        self.cart_tree.column("Subtotal", width=65, anchor="e")
        self.cart_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        self.lbl_total_val = ttk.Label(right_frame, text="$ 0.00", font=("Arial", 16, "bold"), foreground="green")
        self.lbl_total_val.pack(pady=5)

        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Borrar Ítem", command=self.quitar_item_carrito).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_frame, text="COBRAR [F6]", command=self.pedir_metodo_pago).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        
        admin_menu = tk.Menu(menu_bar, tearoff=0)
        admin_menu.add_command(label="Gestionar Categorías", command=self.abrir_ventana_categorias)
        admin_menu.add_command(label="Gestionar Inventario", command=self.abrir_ventana_inventario)
        admin_menu.add_separator()
        admin_menu.add_command(label="Imprimir Informe X (Parcial)", command=self.imprimir_informe_x)
        admin_menu.add_command(label="Imprimir Cierre de Caja y Resetear", command=self.imprimir_cierre_caja)
        menu_bar.add_cascade(label="Administración", menu=admin_menu)

    def load_categories(self):
        for tab in self.notebook_categorias.tabs():
            self.notebook_categorias.forget(tab)

        cursor = self.db.query("SELECT id, nombre_categoria FROM categorias")
        categorias = cursor.fetchall()

        if not categorias:
            frame_vacio = ttk.Frame(self.notebook_categorias)
            self.notebook_categorias.add(frame_vacio, text="Sin Categorías")
            ttk.Label(frame_vacio, text="Vaya a Administración > Gestionar Categorías para crear una.", font=("Arial", 10)).pack(pady=20)
            return

        for cat_id, cat_nombre in categorias:
            cat_frame = ttk.Frame(self.notebook_categorias)
            self.notebook_categorias.add(cat_frame, text=cat_nombre)
            self.cargar_slots_productos(cat_frame, cat_id)

    def cargar_slots_productos(self, parent_frame, categoria_id):
        cursor = self.db.query("SELECT id, nombre, precio FROM productos WHERE id_categoria = ?", (categoria_id,))
        productos = cursor.fetchall()

        grid_frame = ttk.Frame(parent_frame, padding=5)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # Grilla de 20 slots (4 filas x 5 columnas)
        for i in range(20):
            row = i // 5
            col = i % 5
            
            if i < len(productos):
                prod_id, nombre, precio = productos[i]
                btn_text = f"{nombre}\n${precio:.0f}"
                btn = tk.Button(grid_frame, text=btn_text, bg="#f0f0f0", font=("Arial", 9, "bold"),
                                command=lambda pid=prod_id, pnom=nombre, pprec=precio: self.agregar_al_carrito(pid, pnom, pprec))
            else:
                btn = tk.Button(grid_frame, text=f"Slot Vacío {i+1}", state=tk.DISABLED, bg="#e0e0e0", font=("Arial", 8))
            
            btn.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)

        for r in range(4):
            grid_frame.rowconfigure(r, weight=1)
        for c in range(5):
            grid_frame.columnconfigure(c, weight=1)

    def agregar_al_carrito(self, producto_id, nombre, precio):
        for item in self.cart:
            if item[0] == producto_id:
                item[3] += 1
                self.actualizar_vista_carrito()
                return
        
        self.cart.append([producto_id, nombre, precio, 1])
        self.actualizar_vista_carrito()

    def quitar_item_carrito(self):
        selected_item = self.cart_tree.selection()
        if not selected_item:
            messagebox.showwarning("Aviso", "Seleccione un ítem del ticket para borrar.")
            return
        index = self.cart_tree.index(selected_item[0])
        del self.cart[index]
        self.actualizar_vista_carrito()

    def actualizar_vista_carrito(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        
        total = 0.0
        for item in self.cart:
            _, nombre, precio, cantidad = item
            subtotal = precio * cantidad
            total += subtotal
            self.cart_tree.insert("", tk.END, values=(cantidad, nombre, f"${subtotal:.0f}"))
        
        self.lbl_total_val.config(text=f"$ {total:.0f}")

    def pedir_metodo_pago(self):
        if not self.cart:
            messagebox.showwarning("Carrito Vacío", "No hay productos en el ticket actual.")
            return

        total_venta = sum(item[2] * item[3] for item in self.cart)

        pago_win = tk.Toplevel(self.root)
        pago_win.title("Seleccionar Método de Pago")
        pago_win.geometry("320x240")
        pago_win.grab_set()

        ttk.Label(pago_win, text=f"TOTAL A PAGAR: ${total_venta:.0f}", font=("Arial", 11, "bold"), foreground="green").pack(pady=10)
        ttk.Label(pago_win, text="Seleccione el método de pago:", font=("Arial", 10)).pack(pady=5)

        def seleccionar(metodo):
            efectivo_recibido = 0.0
            vuelto = 0.0

            if metodo == "EFECTIVO":
                monto_str = simpledialog.askstring("Pago en Efectivo", f"Total a pagar: ${total_venta:.0f}\nIngrese con cuánto dinero paga:", parent=pago_win)
                if not monto_str:
                    return 
                try:
                    efectivo_recibido = float(monto_str)
                    if efectivo_recibido < total_venta:
                        messagebox.showerror("Error", "El monto ingresado es menor al total de la venta.")
                        return
                    vuelto = efectivo_recibido - total_venta
                    messagebox.showinfo("Cálculo de Vuelto", f"Total: ${total_venta:.0f}\nPago: ${efectivo_recibido:.0f}\n\n>>> VUELTO A DAR: ${vuelto:.0f} <<<")
                except ValueError:
                    messagebox.showerror("Error", "Ingrese un valor numérico válido.")
                    return

            pago_win.destroy()
            self.procesar_cobro(metodo, efectivo_recibido, vuelto)

        ttk.Button(pago_win, text="EFECTIVO", command=lambda: seleccionar("EFECTIVO")).pack(fill=tk.X, padx=30, pady=5)
        ttk.Button(pago_win, text="DEBITO", command=lambda: seleccionar("DEBITO")).pack(fill=tk.X, padx=30, pady=5)
        ttk.Button(pago_win, text="CREDITO", command=lambda: seleccionar("CREDITO")).pack(fill=tk.X, padx=30, pady=5)

    def procesar_cobro(self, metodo_pago, efectivo_recibido, vuelto):
        total_venta = sum(item[2] * item[3] for item in self.cart)
        ahora = datetime.datetime.now()
        fecha_actual = ahora.strftime("%d/%m/%Y %H:%M") + " Hrs."

        cursor = self.db.query("INSERT INTO ventas (fecha, total, metodo_pago, cerrado) VALUES (?, ?, ?, 0)", 
                               (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_venta, metodo_pago))
        venta_id = cursor.lastrowid

        for item in self.cart:
            prod_id, _, _, cantidad = item
            self.db.query("INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
                          (venta_id, prod_id, cantidad, item[2]))

        self.enviar_impresion_ticket(venta_id, fecha_actual, total_venta, metodo_pago, efectivo_recibido, vuelto, metodo_pago == "EFECTIVO")

        self.cart = []
        self.actualizar_vista_carrito()
        messagebox.showinfo("Éxito", "Venta procesada e impresa correctamente.")

    def enviar_impresion_ticket(self, venta_id, fecha, total, metodo_pago, efectivo_recibido, vuelto, es_efectivo=False):
        try:
            lineas = []
            lineas.append("\n\n")  # Margen superior
            
            lineas.append("--------------------------------\n")
            lineas.append(">>   GELATERIA  MERY  MOLOY  <<\n")
            lineas.append("      GRACIAS POR SU VISITA\n")
            lineas.append("-------- VALE DE CONTROL INTERNO --------\n\n")
            
            lineas.append(f"CAJA 0001   VEND: 1 MERY MOLOY\n")
            lineas.append(f"VALE {venta_id:06d}    {fecha}\n\n")
            
            # Detalle con nombre ampliado a 16 caracteres para aprovechar el ancho del ticket
            for item in self.cart:
                _, nombre, precio, cantidad = item
                subtotal = precio * cantidad
                lineas.append(f"{nombre[:16]:16} x{cantidad:<2}    $ {subtotal:5.0f}\n")
            
            lineas.append(f"\n{metodo_pago:<15}    $ {total:6.0f}\n")
            
            if metodo_pago == "EFECTIVO":
                lineas.append(f"EFECTIVO REC.     $ {efectivo_recibido:6.0f}\n")
                lineas.append(f"SU VUELTO         $ {vuelto:6.0f}\n")
            
            lineas.append(f"\nTOTAL  $ {total:.0f}\n\n")
            lineas.append("\n\n\n")  # Margen inferior
            
            contenido_texto = "".join(lineas).encode("latin-1")
            
            comando_corte = b'\x1d\x56\x41\x00'
            comando_cajon = b'\x1b\x70\x00\x19\xfa'
            
            with open("print_temp.txt", "wb") as f:
                f.write(contenido_texto)
                if es_efectivo:
                    f.write(comando_cajon)
                f.write(comando_corte)
            
            os.system(f'copy /b print_temp.txt {DESTINO_IMPRESORA}')
            
        except Exception as e:
            messagebox.showwarning("Aviso de Impresión", f"Venta guardada, pero hubo un problema al imprimir:\n{str(e)}")

    def imprimir_informe_x(self):
        self._generar_reporte(resetear=False, titulo_reporte="Informe X (Parcial)")

    def imprimir_cierre_caja(self):
        self._generar_reporte(resetear=True, titulo_reporte="Cierre de Caja (Informe Z)")

    def _generar_reporte(self, resetear=False, titulo_reporte="Informe"):
        try:
            cursor = self.db.query("""
                SELECT metodo_pago, COUNT(id), SUM(total) 
                FROM ventas 
                WHERE cerrado = 0 
                GROUP BY metodo_pago
            """)
            resultados = cursor.fetchall()
            
            datos_pagos = {"EFECTIVO": {"ops": 0, "total": 0.0}, "DEBITO": {"ops": 0, "total": 0.0}, "CREDITO": {"ops": 0, "total": 0.0}}
            total_general = 0.0
            
            for metodo, ops, tot in resultados:
                m_upper = metodo.upper()
                if m_upper in datos_pagos:
                    datos_pagos[m_upper]["ops"] = ops
                    datos_pagos[m_upper]["total"] = tot
                total_general += tot

            fecha_informe = datetime.datetime.now().strftime("%d/%m/%Y %H:%M") + " Hrs."
            
            lineas = []
            lineas.append("\n\n")
            lineas.append("--------------------------------\n")
            lineas.append(">>   GELATERIA  MERY  MOLOY  <<\n")
            lineas.append(f"-------- {titulo_reporte} --------\n\n")
            
            lineas.append("LOCAL 1   CAJA 0001\n")
            lineas.append("Usuario : Supervisor Caja\n\n")
            lineas.append(f"Fecha: {fecha_informe}\n\n")
            
            lineas.append("EFECTIVO\n")
            lineas.append(f"( {datos_pagos['EFECTIVO']['ops']} operaciones )\n")
            lineas.append(f"          Total Venta      $    {datos_pagos['EFECTIVO']['total']:6.0f}\n\n")
            
            lineas.append("DEBITO\n")
            lineas.append(f"( {datos_pagos['DEBITO']['ops']} operaciones )\n")
            lineas.append(f"          Total Venta      $    {datos_pagos['DEBITO']['total']:6.0f}\n\n")

            lineas.append("CREDITO\n")
            lineas.append(f"( {datos_pagos['CREDITO']['ops']} operaciones )\n")
            lineas.append(f"          Total Venta      $    {datos_pagos['CREDITO']['total']:6.0f}\n\n")
            
            lineas.append("--------------------------------\n")
            lineas.append(f"*** VENTA TOTAL *** $    {total_general:.0f}\n")
            lineas.append("--------------------------------\n\n\n")
            lineas.append("\n\n\n")

            contenido_texto = "".join(lineas).encode("latin-1")
            comando_corte = b'\x1d\x56\x41\x00'

            with open("print_temp.txt", "wb") as f:
                f.write(contenido_texto)
                f.write(comando_corte)
            
            os.system(f'copy /b print_temp.txt {DESTINO_IMPRESORA}')

            if resetear:
                self.db.query("UPDATE ventas SET cerrado = 1 WHERE cerrado = 0")
                messagebox.showinfo("Éxito", "Cierre de caja impreso y acumulado reseteado correctamente.")
            else:
                messagebox.showinfo("Éxito", "Informe X impreso correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir el reporte:\n{str(e)}")

    def abrir_ventana_categorias(self):
        cat_win = tk.Toplevel(self.root)
        cat_win.title("Gestión de Categorías")
        cat_win.geometry("300x200")
        cat_win.grab_set()

        ttk.Label(cat_win, text="Nombre de la Nueva Categoría:").pack(pady=10)
        txt_nombre = ttk.Entry(cat_win, width=25)
        txt_nombre.pack(pady=5)

        def guardar_cat():
            nombre = txt_nombre.get().strip()
            if nombre:
                try:
                    self.db.query("INSERT INTO categorias (nombre_categoria) VALUES (?)", (nombre,))
                    self.load_categories()
                    messagebox.showinfo("Éxito", f"Categoría '{nombre}' creada.")
                    cat_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo crear: {e}")

        ttk.Button(cat_win, text="Guardar Categoría", command=guardar_cat).pack(pady=15)

    def abrir_ventana_inventario(self):
        inv_win = tk.Toplevel(self.root)
        inv_win.title("Gestión de Inventario y Precios")
        inv_win.geometry("750x480")
        inv_win.grab_set()

        tree = ttk.Treeview(inv_win, columns=("ID", "Código", "Nombre", "Cat ID", "Precio"), show="headings")
        for col in ("ID", "Código", "Nombre", "Cat ID", "Precio"):
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def cargar_inv():
            for row in tree.get_children():
                tree.delete(row)
            cursor = self.db.query("SELECT id, codigo, nombre, id_categoria, precio FROM productos")
            for row in cursor.fetchall():
                tree.insert("", tk.END, values=row)

        cargar_inv()

        form = ttk.LabelFrame(inv_win, text="Registrar o Modificar Producto", padding=10)
        form.pack(fill=tk.X, padx=5, pady=5)

        id_producto_editando = tk.IntVar(value=0)

        ttk.Label(form, text="Código:").grid(row=0, column=0, sticky="w")
        e_cod = ttk.Entry(form, width=10)
        e_cod.grid(row=0, column=1, padx=3)

        ttk.Label(form, text="Nombre:").grid(row=0, column=2, sticky="w")
        e_nom = ttk.Entry(form, width=14)
        e_nom.grid(row=0, column=3, padx=3)

        ttk.Label(form, text="Cat ID:").grid(row=0, column=4, sticky="w")
        e_cat = ttk.Entry(form, width=5)
        e_cat.grid(row=0, column=5, padx=3)

        ttk.Label(form, text="Precio:").grid(row=1, column=0, sticky="w", pady=5)
        e_pre = ttk.Entry(form, width=10)
        e_pre.grid(row=1, column=1, padx=3, pady=5)

        def cargar_datos_seleccionado(event):
            selected = tree.selection()
            if not selected:
                return
            item_vals = tree.item(selected[0], "values")
            id_producto_editando.set(int(item_vals[0]))
            
            e_cod.delete(0, tk.END)
            e_cod.insert(0, item_vals[1])
            
            e_nom.delete(0, tk.END)
            e_nom.insert(0, item_vals[2])
            
            e_cat.delete(0, tk.END)
            e_cat.insert(0, item_vals[3])
            
            e_pre.delete(0, tk.END)
            e_pre.insert(0, item_vals[4])

        tree.bind("<<TreeviewSelect>>", cargar_datos_seleccionado)

        def guardar_o_actualizar_prod():
            try:
                codigo = e_cod.get().strip()
                nombre = e_nom.get().strip()
                id_cat = int(e_cat.get())
                precio = float(e_pre.get())
                prod_id = id_producto_editando.get()

                if not codigo or not nombre:
                    messagebox.showwarning("Aviso", "Complete el código y el nombre del producto.")
                    return

                if prod_id == 0:
                    self.db.query("INSERT INTO productos (codigo, nombre, id_categoria, precio) VALUES (?, ?, ?, ?)",
                                  (codigo, nombre, id_cat, precio))
                    messagebox.showinfo("Éxito", "Producto registrado en el inventario.")
                else:
                    self.db.query("UPDATE productos SET codigo = ?, nombre = ?, id_categoria = ?, precio = ? WHERE id = ?",
                                  (codigo, nombre, id_cat, precio, prod_id))
                    messagebox.showinfo("Éxito", "Producto actualizado correctamente.")
                    id_producto_editando.set(0)

                e_cod.delete(0, tk.END)
                e_nom.delete(0, tk.END)
                e_cat.delete(0, tk.END)
                e_pre.delete(0, tk.END)

                cargar_inv()
                self.load_categories()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar: {e}")

        def limpiar_formulario():
            id_producto_editando.set(0)
            e_cod.delete(0, tk.END)
            e_nom.delete(0, tk.END)
            e_cat.delete(0, tk.END)
            e_pre.delete(0, tk.END)

        ttk.Button(form, text="Guardar / Actualizar", command=guardar_o_actualizar_prod).grid(row=1, column=4, padx=5)
        ttk.Button(form, text="Limpiar Form", command=limpiar_formulario).grid(row=1, column=5, padx=5)


if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()