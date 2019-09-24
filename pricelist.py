# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2004-2010 Tiny SPRL (http://tiny.be). All Rights Reserved
#    
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/.
#
##############################################################################
from openerp.osv import fields, osv
from _common import rounding
#from openerp import rounding
import time
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

__author__ = "NEXTMA"
__version__ = "0.1"
#__date__ = u"29 décembre 2013"

class product_pricelist(osv.osv):
    u"""Gestion des listes de prix des produits"""
    _name = "product.pricelist"
    _inherit = "product.pricelist"
    _description = u'Gestion des listes de prix des produits'
 
    def make_child_list_tree_category(self,cr,uid,object_category_id,lst=[],context=None):
        u"""Etablir l'hierarchie des liste de prix par catégorie"""
        object_category=self.pool.get('product.category').browse(cr,uid,object_category_id)
        if not object_category:
            return []
        if object_category.id not in lst:
            lst.append(object_category.id)
            for object_child_category in object_category.child_id:
                return self.make_child_list_tree_category(cr,uid,object_child_category.id,lst)  
        return lst
        
    def make_list_product_id_from_category_list(self,cr,uid,category_list):
        lst=[]
        for id_category in category_list:
            ids_product=self.pool.get('product.product').search(cr,uid,[('categ_id','=',id_category)])
            lst.extend([i for i in ids_product if i not in lst])
        return lst
    
    def get_list_product_from_version(self,cr,uid,version_id):
        u"""Récupérer la liste des produits d"une version"""
        lst=[]
        ids_pricelist_item=self.pool.get('product.pricelist.item').search(cr,uid,[('price_version_id','=',version_id)])
        list_object_item=self.pool.get('product.pricelist.item').browse(cr,uid,ids_pricelist_item)
        for object_item in list_object_item:
            if object_item.product_id:
                if object_item.product_id.id not in lst:
                    lst.append(object_item.product_id.id)
            if object_item.categ_id:
                data_id_categ=[]
                data_id_categ=self.make_child_list_tree_category(cr,uid,object_item.categ_id.id)
                data_id_product=self.make_list_product_id_from_category_list(cr, uid, data_id_categ)
                lst.extend([i for i in data_id_product if i not in lst])
        return lst


    def price_get_multi_travel(self, cr, uid, pricelist_ids, products_by_qty_by_partner,merchandise_id=False, context=None):
        u"""Prix d'un trajet selon les listes de prix.
           @param pricelist_ids:
           @param merchandise_id:
           @param products_by_qty:
           @param partner:
           @param context: {
             'date': Date of the pricelist (%Y-%m-%d),}
           @return: a dict of dict with product_id as key and a dict 'price by pricelist' as value
        """
        list_product=[]
        def _create_parent_category_list(id, lst):
            if not id:
                return []
            parent = product_category_tree.get(id)
            if parent:
                lst.append(parent)
                return _create_parent_category_list(parent, lst)
            else:
                return lst
        # _create_parent_category_list

        if context is None:
            context = {}

        date = context.get('date') or time.strftime('%Y-%m-%d')
        #if 'date' in context:
        #    date = context['date']
        currency_obj = self.pool.get('res.currency')
        product_obj = self.pool.get('product.product')
        #product_template_obj = self.pool.get('product.template')
        product_category_obj = self.pool.get('product.category')
        product_uom_obj = self.pool.get('product.uom')
        supplierinfo_obj = self.pool.get('product.supplierinfo')
        price_type_obj = self.pool.get('product.price.type')
        comission_merchandise=0
        # product.pricelist.version:
        if not pricelist_ids:
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [], context=context)
        pricelist_version_ids = self.pool.get('product.pricelist.version').search(cr, uid, [
                                                        ('pricelist_id', 'in', pricelist_ids),
                                                        '|',
                                                        ('date_start', '=', False),
                                                        ('date_start', '<=', date),
                                                        '|',
                                                        ('date_end', '=', False),
                                                        ('date_end', '>=', date),
                                                    ])
        if len(pricelist_ids) != len(pricelist_version_ids):
            raise osv.except_osv(_('Attention !'), _(u"Il y'a au moins une liste de prix sans version active !\nVeuillez s'il vous plaît créer ou activer une."))

        # product.product:
        product_ids = [i[0] for i in products_by_qty_by_partner]
        #products = dict([(item['id'], item) for item in product_obj.read(cr, uid, product_ids, ['categ_id', 'product_tmpl_id', 'uos_id', 'uom_id'])])
        products = product_obj.browse(cr, uid, product_ids, context=context)
        products_dict = dict([(item.id, item) for item in products])

        # product.category:
        product_category_ids = product_category_obj.search(cr, uid, [])
        product_categories = product_category_obj.read(cr, uid, product_category_ids, ['parent_id'])
        product_category_tree = dict([(item['id'], item['parent_id'][0]) for item in product_categories if item['parent_id']])
        results = {}
        for product_id, qty, partner in products_by_qty_by_partner:
            for pricelist_id in pricelist_ids:
                price = False
                tmpl_id = products_dict[product_id].product_tmpl_id and products_dict[product_id].product_tmpl_id.id or False
                categ_id = products_dict[product_id].categ_id and products_dict[product_id].categ_id.id or False
                categ_ids = _create_parent_category_list(categ_id, [categ_id])
                if categ_ids:
                    categ_where = '(categ_id IN (' + ','.join(map(str, categ_ids)) + '))'
                else:
                    categ_where = '(categ_id IS NULL)'
                if partner:
                    partner_where = 'base <> -2 OR %s IN (SELECT name FROM product_supplierinfo WHERE product_id = %s) '
                    partner_args = (partner, tmpl_id) # product_id -> tmpl_id
                else:
                    partner_where = 'base <> -2 '
                    partner_args = ()
                if tmpl_id:
                    cr.execute(
                    'SELECT i.*, pl.currency_id '
                    'FROM product_pricelist_item AS i, '
                        'product_pricelist_version AS v, product_pricelist AS pl '
                    'WHERE (product_tmpl_id IS NULL OR product_tmpl_id = %s) '
                        'AND (product_id IS NULL OR product_id = %s) '
                        'AND (' + categ_where + ' OR (categ_id IS NULL)) '
                        'AND (' + partner_where + ') '
                        'AND price_version_id = %s '
                        'AND (min_quantity IS NULL OR min_quantity <= %s) '
                        'AND i.price_version_id = v.id AND v.pricelist_id = pl.id '
                    'ORDER BY sequence',
                    (tmpl_id, product_id) + partner_args + (pricelist_version_ids[0], qty))
                res1 = cr.dictfetchall()
                uom_price_already_computed = False
                for res in res1:
                    if res:
                        if res['base'] == -1:
                            if not res['base_pricelist_id']:
                                price = 0.0
                            else:
                                price_tmp = self.price_get(cr, uid,
                                        [res['base_pricelist_id']], product_id,
                                        qty, context=context)[res['base_pricelist_id']]
                                ptype_src = self.browse(cr, uid, res['base_pricelist_id']).currency_id.id
                                uom_price_already_computed = True
                                price = currency_obj.compute(cr, uid,
                                        ptype_src, res['currency_id'],
                                        price_tmp, round=False,
                                        context=context)
                        elif res['base'] == -2:
                            # this section could be improved by moving the queries outside the loop:
                            where = []
                            if partner:
                                where = [('name', '=', partner) ]
                            sinfo = supplierinfo_obj.search(cr, uid,
                                    [('product_id', '=', tmpl_id)] + where)
                            price = 0.0
                            if sinfo:
                                qty_in_product_uom = qty
                                product_default_uom = product_obj.read(cr, uid, [product_id], ['uom_id'])[0]['uom_id'][0]
                                supplier = supplierinfo_obj.browse(cr, uid, sinfo, context=context)[0]
                                seller_uom = supplier.product_uom and supplier.product_uom.id or False
                                if seller_uom and product_default_uom and product_default_uom != seller_uom:
                                    uom_price_already_computed = True
                                    qty_in_product_uom = product_uom_obj._compute_qty(cr, uid, product_default_uom, qty, to_uom_id=seller_uom)
                                cr.execute('SELECT * ' \
                                        'FROM pricelist_partnerinfo ' \
                                        'WHERE suppinfo_id IN %s' \
                                            'AND min_quantity <= %s ' \
                                        'ORDER BY min_quantity DESC LIMIT 1', (tuple(sinfo),qty_in_product_uom,))
                                res2 = cr.dictfetchone()
                                if res2:
                                    price = res2['price']
                        else:
                            price_type = price_type_obj.browse(cr, uid, int(res['base']))
                            uom_price_already_computed = True
                            price = currency_obj.compute(cr, uid,
                                    price_type.currency_id.id, res['currency_id'],
                                    product_obj.price_get(cr, uid, [product_id],
                                    price_type.field, context=context)[product_id], round=False, context=context)
                        if price is not False:
                            price_limit = price
                            price = price * (1.0+(res['price_discount'] or 0.0))
                            price = rounding(price, res['price_round']) #TOFIX: rounding with tools.float_rouding
                            price += (res['price_surcharge'] or 0.0)
                            if res['price_min_margin']:
                                price = max(price, price_limit+res['price_min_margin'])
                            if res['price_max_margin']:
                                price = min(price, price_limit+res['price_max_margin'])
                            price_merchandise=self.pool.get('product.pricelist.item').get_total_price_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                            comission_merchandise=self.pool.get('product.pricelist.item').get_comission_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                            comission_is_fixes= self.pool.get('product.pricelist.item').get_comission_is_fixed(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                            comission_fixe= self.pool.get('product.pricelist.item').get_comission_fixe(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                            if price_merchandise:
                                price = price_merchandise
                                comission=comission_merchandise
                            break
                    else:
                        # False means no valid line found ! But we may not raise an
                        # exception here because it breaks the search
                        price = False
                if price:
                    results['item_id'] = res['id']
                    if 'uom' in context and not uom_price_already_computed:
                        product = products_dict[product_id]
                        uom = product.uos_id or product.uom_id
                        price = product_uom_obj._compute_price(cr, uid, uom.id, price, context['uom'])
                        price_merchandise=self.pool.get('product.pricelist.item').get_total_price_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                        comission_merchandise=self.pool.get('product.pricelist.item').get_comission_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                        comission_is_fixes= self.pool.get('product.pricelist.item').get_comission_is_fixed(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                        comission_fixe= self.pool.get('product.pricelist.item').get_comission_fixe(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                         

                        if price_merchandise:
                            price = price_merchandise
                if results.get(product_id):
                    results[product_id][pricelist_id] = price
                else:
                    results['comission_merchandise']=comission_merchandise
                    try :
                        results['comission_is_fixe']=comission_is_fixes
                        results['comission_fixe']=comission_fixe
                    except :
                        pass
                    results[product_id] = {pricelist_id: price}
        return results

    def price_get_travel(self, cr, uid, ids, prod_id, qty, partner=None,merchandise_id=False, context=None):
        u"""Calcul du prix de voyage"""
        res_multi = self.price_get_multi_travel(cr, uid, pricelist_ids=ids, products_by_qty_by_partner=[(prod_id, qty, partner)],merchandise_id=merchandise_id, context=context)
        res = res_multi[prod_id]
        res.update({'comission':res_multi.get('comission_merchandise'),'comission_is_fixe':res_multi.get('comission_is_fixe'),'comission_fixe':res_multi.get('comission_fixe'),'item_id': {ids[-1]: res_multi.get('item_id', ids[-1])}})
        return res

    def commission_get_multi(self, cr, uid, pricelist_ids, products_by_qty_by_partner,merchandise_id=False, context=None):
        u"""Calcul de la commission en fonction des listes de prix.
           @param pricelist_ids:
           @param products_by_qty:
           @param partner:
           @param context: {
             'date': Date of the pricelist (%Y-%m-%d),}
           @return: a dict of dict with product_id as key and a dict 'price by pricelist' as value
        """
        def _create_parent_category_list(id, lst):
            if not id:
                return []
            parent = product_category_tree.get(id)
            if parent:
                lst.append(parent)
                return _create_parent_category_list(parent, lst)
            else:
                return lst
        # _create_parent_category_list
        if context is None:
            context = {}
        date = time.strftime('%Y-%m-%d')
        if 'date' in context:
            date = context['date']
        currency_obj = self.pool.get('res.currency')
        product_obj = self.pool.get('product.product')
        #product_template_obj = self.pool.get('product.template')
        product_category_obj = self.pool.get('product.category')
        product_uom_obj = self.pool.get('product.uom')
        supplierinfo_obj = self.pool.get('product.supplierinfo')
        price_type_obj = self.pool.get('product.price.type')

        # product.pricelist.version:
        if not pricelist_ids:
            pricelist_ids = self.pool.get('product.pricelist').search(cr, uid, [], context=context)
        pricelist_version_ids = self.pool.get('product.pricelist.version').search(cr, uid, [
                                                        ('pricelist_id', 'in', pricelist_ids),
                                                        '|',
                                                        ('date_start', '=', False),
                                                        ('date_start', '<=', date),
                                                        '|',
                                                        ('date_end', '=', False),
                                                        ('date_end', '>=', date),
                                                    ])
        if len(pricelist_ids) != len(pricelist_version_ids):
            raise osv.except_osv(_('Warning !'), _("At least one pricelist has no active version !\nPlease create or activate one."))

        # product.product:
        product_ids = [i[0] for i in products_by_qty_by_partner]
        products = product_obj.browse(cr, uid, product_ids, context=context)
        products_dict = dict([(item.id, item) for item in products])

        # product.category:
        product_category_ids = product_category_obj.search(cr, uid, [])
        product_categories = product_category_obj.read(cr, uid, product_category_ids, ['parent_id'])
        product_category_tree = dict([(item['id'], item['parent_id'][0]) for item in product_categories if item['parent_id']])
        fixed=True
        commission_value_type=0
        results = {}
        for product_id, qty, partner in products_by_qty_by_partner:
            for pricelist_id in pricelist_ids:
                price = False
                commission=False
                
                #template _id
                tmpl_id = products_dict[product_id].product_tmpl_id and products_dict[product_id].product_tmpl_id.id or False
                categ_id = products_dict[product_id].categ_id and products_dict[product_id].categ_id.id or False
                categ_ids = _create_parent_category_list(categ_id, [categ_id])
                if categ_ids:
                    categ_where = '(categ_id IN (' + ','.join(map(str, categ_ids)) + '))'
                else:
                    categ_where = '(categ_id IS NULL)'
                if partner:
                    partner_where = 'base <> -2 OR %s IN (SELECT name FROM product_supplierinfo WHERE product_id = %s) '
                    partner_args = (partner, tmpl_id) # product_id -> tmpl_id
                else:
                    partner_where = 'base <> -2 '
                    partner_args = ()
                cr.execute(
                    'SELECT i.*, pl.currency_id '
                    'FROM product_pricelist_item AS i, '
                        'product_pricelist_version AS v, product_pricelist AS pl '
                    'WHERE (product_tmpl_id IS NULL OR product_tmpl_id = %s) '
                        'AND (product_id IS NULL OR product_id = %s) '
                        'AND (' + categ_where + ' OR (categ_id IS NULL)) '
                        'AND (' + partner_where + ') '
                        'AND price_version_id = %s '
                        'AND (min_quantity IS NULL OR min_quantity <= %s) '
                        'AND i.price_version_id = v.id AND v.pricelist_id = pl.id '
                    'ORDER BY sequence',
                    (tmpl_id, product_id) + partner_args + (pricelist_version_ids[0], qty))
                res1 = cr.dictfetchall()
                uom_price_already_computed = False
                for res in res1:
                    if res:## calcul du prix
                        if res['base'] == -1:
                            if not res['base_pricelist_id']:
                                price = 0.0
                            else:
                                price_tmp = self.price_get(cr, uid,
                                        [res['base_pricelist_id']], product_id,
                                        qty, context=context)[res['base_pricelist_id']]
                                ptype_src = self.browse(cr, uid, res['base_pricelist_id']).currency_id.id
                                uom_price_already_computed = True
                                price = currency_obj.compute(cr, uid,
                                        ptype_src, res['currency_id'],
                                        price_tmp, round=False,
                                        context=context)
                        elif res['base'] == -2:
                            # this section could be improved by moving the queries outside the loop:
                            where = []
                            if partner:
                                where = [('name', '=', partner) ]
                            sinfo = supplierinfo_obj.search(cr, uid,
                                    [('product_id', '=', tmpl_id)] + where)
                            price = 0.0
                            if sinfo:
                                qty_in_product_uom = qty
                                product_default_uom = product_obj.read(cr, uid, [product_id], ['uom_id'])[0]['uom_id'][0]
                                supplier = supplierinfo_obj.browse(cr, uid, sinfo, context=context)[0]
                                seller_uom = supplier.product_uom and supplier.product_uom.id or False
                                if seller_uom and product_default_uom and product_default_uom != seller_uom:
                                    uom_price_already_computed = True
                                    qty_in_product_uom = product_uom_obj._compute_qty(cr, uid, product_default_uom, qty, to_uom_id=seller_uom)
                                cr.execute('SELECT * ' \
                                        'FROM pricelist_partnerinfo ' \
                                        'WHERE suppinfo_id IN %s' \
                                            'AND min_quantity <= %s ' \
                                        'ORDER BY min_quantity DESC LIMIT 1', (tuple(sinfo),qty_in_product_uom,))
                                res2 = cr.dictfetchone()
                                if res2:
                                    price = res2['price']
                        else:
                            price_type = price_type_obj.browse(cr, uid, int(res['base']))
                            uom_price_already_computed = True
                            price = currency_obj.compute(cr, uid,
                                    price_type.currency_id.id, res['currency_id'],
                                    product_obj.price_get(cr, uid, [product_id],
                                    price_type.field, context=context)[product_id], round=False, context=context)
                        if price is not False:
                            price_limit = price
                            price = price * (1.0+(res['price_discount'] or 0.0))
                            price = rounding(price, res['price_round']) #TOFIX: rounding with tools.float_rouding
                            price += (res['price_surcharge'] or 0.0)
                            if res['price_min_margin']:
                                price = max(price, price_limit+res['price_min_margin'])
                            if res['price_max_margin']:
                                price = min(price, price_limit+res['price_max_margin'])
                            price_merchandise=self.pool.get('product.pricelist.item').get_total_price_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                            if price_merchandise:                        
                                price = price_merchandise
                            if res['commission_ok'] == True:    
                                commission = 0
                                if res['fixed_commission_ok'] == True:
                                    commission_limit = commission
                                    object_product=product_obj.browse(cr,uid,product_id)
                                    if object_product:
                                        commission=object_product.rate_commission
                                        commission = commission * (1.0+(res['price_discount_commission'] or 0.0))
                                        commission = rounding(commission, res['price_round_commission']) #TOFIX: rounding with tools.float_rouding
                                        commission += (res['price_surcharge_commission'] or 0.0)
                                        if res['price_min_margin_commission']:
                                            commission = max(commission, commission_limit+res['price_min_margin_commission'])
                                        if res['price_max_margin_commission']:
                                            commission = min(commission, commission_limit+res['price_max_margin_commission'])
                                    commission_value_type=commission
                                    break
                                elif res['percent_commission_ok'] == True:
                                    fixed=False
                                    commission=(price*res['percent_commission']) / 100
                                    commission_value_type = res['percent_commission']
                            else:
                                object_product=product_obj.browse(cr,uid,product_id)
                                data_commission=self.pool.get('product.product').get_base_commission(cr,uid,product_id)
                                commission = data_commission['commission']
                                fixed = data_commission['fixed']
                                commission_value_type = data_commission['commission_value_type']
                    else:
                        price = False
                if price:
                    results['item_id'] = res['id']
                    if 'uom' in context and not uom_price_already_computed:
                        product = products_dict[product_id]
                        uom = product.uos_id or product.uom_id
                        price = product_uom_obj._compute_price(cr, uid, uom.id, price, context['uom'])
                        commission = 0
                        object_product=product_obj.browse(cr,uid,product_id)
                        price_merchandise=self.pool.get('product.pricelist.item').get_total_price_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                        comission_merchandise=self.pool.get('product.pricelist.item').get_comission_merchandise(cr,uid,pricelist_version_ids[0],product_id,merchandise_id)
                        if price_merchandise:                                
                            price = price_merchandise
                        if res['commission_ok'] == True:
                            if res['fixed_commission_ok'] == True:
                                commission_limit = commission     
                                fixed=True      
                                if object_product:
                                    commission=object_product.get_base_commission(cr,uid,object_product.id)
                                    commission = commission * (1.0+(res['price_discount_commission'] or 0.0))
                                    commission = rounding(commission, res['price_round_commission']) #TOFIX: rounding with tools.float_rouding
                                    commission += (res['price_surcharge_commission'] or 0.0)
                                    if res['price_min_margin_commission']:
                                        commission = max(commission, commission_limit+res['price_min_margin_commission'])
                                    if res['price_max_margin_commission']:
                                        commission = min(commission, commission_limit+res['price_max_margin_commission'])
                                break
                                commission_value_type=commission
                            elif res['percent_commission_ok'] == True:
                                fixed=False 
                                commission=(price*res['percent_commission']) / 100
                                commission_value_type = res['percent_commission']
                        else:
                            data_commission=object_product.get_base_commission(cr,uid,object_product.id)
                            commission = data_commission['commission']
                            fixed = data_commission['fixed']
                            commission_value_type = data_commission['commission_value_type']
                if results.get(product_id):
                    results[product_id][pricelist_id] = {
                                                         'commission' : commission,
                                                         'fixed' : fixed,
                                                         'commission_value_type' : commission_value_type,
                                                         }
                else:
                    results[product_id] = {pricelist_id: {
                                                         'commission' : commission,
                                                         'fixed' : fixed,
                                                         'commission_value_type' : commission_value_type,
                                                         }}
        return results

    def commission_get(self, cr, uid, ids, prod_id, qty, partner=None,merchandise_id=False, context=None):
        u"""Calcul des commissions"""
        res_multi = self.commission_get_multi(cr, uid, pricelist_ids=ids, products_by_qty_by_partner=[(prod_id, qty, partner)],merchandise_id=merchandise_id, context=context)
        res = res_multi[prod_id]
        res.update({'item_id': {ids[-1]: res_multi.get('item_id', ids[-1])}})
        return res

    _columns = {
    }

class product_pricelist_item_merchandise(osv.osv):
    u"""Classe pour la tarification dans la liste de prix en fonction du type de transport."""
    
    _name = 'product.pricelist.item.merchandise'
    _description = u'tarification en fonction du type de transport.'
    _columns = {
            'merchandise_id' : fields.many2one('tms.travel.palet.merchandise', u'type de transport',help=u"Type de transport utilisé(exemple, 1-2 tonnes, Maïs)"),
            'price' : fields.float(u'Prix supplémentaire',required=True,help=u"Prix unitaire pour le type de transport associé à ce trajet"),
            'pricelist_item_id' : fields.many2one('product.pricelist.item',u'item liste de prix',help=u"ligne de liste de prix associée"),
            'comission' : fields.float(u'Comission'),
            'fixe':fields.boolean(u'Comission fixe?'),
            'comission_fixe':fields.float(u'Comission fixe'),
            'uom_id' : fields.many2one('product.uom','Unité de livraison',required=True),
            'min_quantity' : fields.integer('Quantité min.'),
            'born_inf' : fields.integer('De'),
            'born_sup' : fields.integer('À'),
            'fixed' : fields.boolean(u'Prix fixe par intervalle?',helps="Cochez cette case si le prix est fixe par intervalle et veuillez préciser l'intervalle."),
                    }
    _defaults = {  
        'price': lambda *a : 0.0, 
        'min_quantity' : lambda *a : 1,    
        }
    
    _sql_constraints = [ 
        ('merchandise_item_uniq', 'unique (pricelist_item_id, merchandise_id)', _(u'Vous ne pouvez pas définir plusieurs fois le type de transport'))
    ]
    
product_pricelist_item_merchandise()

class product_pricelist_item(osv.osv):
    u"""Prix du produit dans la liste de prix"""
    
    _name = "product.pricelist.item"
    _inherit = 'product.pricelist.item' 
    
    def _price_field_get(self, cr, uid, context=None):
        pt = self.pool.get('product.price.type')
        ids = pt.search(cr, uid, [], context=context)
        result = []
        for line in pt.browse(cr, uid, ids, context=context):
            result.append((line.id, line.name))
        result.append((-1, _('Other Pricelist')))
        result.append((-2, _('Partner section of the product form')))
        return result

    _columns = {
        'fixed' : fields.boolean('Prix fixe'),
        'commission_ok' : fields.boolean(u'Commission chauffeur',help=u"Cochez pour paramétrez la commission du chauffeur sur le trajet"),
        'fixed_commission_ok' : fields.boolean(u'Commission fixe',help=u"Définir une commission fixe pour le chauffeur"),
        'percent_commission_ok' : fields.boolean(u'Commission en pourcentage',help=u"Définir une commission variant selon le coût du voyage"),
        'percent_commission' : fields.float(u'Pourcentage commission',help=u"Commission en pourcentage variant selon le coût du voyage"),
        'price_surcharge_commission': fields.float(u'Prix de surcharge commission', digits_compute= dp.get_precision('Sale Price'),help=u"Surplus commission"),
        'price_discount_commission': fields.float(u'Prix de réduction commission', digits=(16,4),help=u"réduction commission"),
        'price_round_commission': fields.float(u'Prix arrondi commission', digits_compute=dp.get_precision('Sale Price')),
        'price_min_margin_commission': fields.float(u'Min. Price Margin', digits_compute= dp.get_precision('Sale Price')),
        'price_max_margin_commission': fields.float(u'Max. Price Margin', digits_compute= dp.get_precision('Sale Price')),
        'trajet_ok' : fields.boolean(u'Voyage'),
        'item_merchandise_ids' : fields.one2many('product.pricelist.item.merchandise','pricelist_item_id', u'supplément type de transport', help=u"Définir les tarifications en fonction du type de transport"),
    }
    _defaults = {
        'commission_ok' : lambda *a : False,
        'price_discount_commission': lambda *a: 0,
        'trajet_ok' : lambda *a : False,
        'fixed_commission_ok' : lambda *a: True,
        'percent_commission_ok' : lambda *a: False,
    }

    def copy(self, cr, uid, id, default=None, context=None):
        u"""méthode de copie"""
        if default is None:
            default = {}
        default = default.copy()
        default.update({'item_merchandise_ids': []})
        return super(product_pricelist_item, self).copy(cr, uid, id, default, context=context)
    
    def get_total_price_merchandise(self,cr,uid,ids,product_id,merchandise_id,context=None):
        u"""Calcul le prix total du type de transport en fonction du trajet"""
        total_price=0
        comission_merchandise=0
        res={}
        if merchandise_id and product_id:
            data_object_pricelist_item = self.search(cr,uid,[('price_version_id','=',ids),('product_id','=',product_id)])
            if  data_object_pricelist_item:
                object_pricelist_item=self.browse(cr,uid,data_object_pricelist_item[0])
                for line_merchendise_id in object_pricelist_item.item_merchandise_ids:
                    if line_merchendise_id.merchandise_id.id==merchandise_id:
                        comission_merchandise=line_merchendise_id.comission
                if object_pricelist_item:
                    for object_item_merchandise in object_pricelist_item.item_merchandise_ids:
                            if merchandise_id == object_item_merchandise.merchandise_id.id:
                                total_price = object_item_merchandise.price
                                res={'total_price':total_price,'comission_marchandise':comission_merchandise}
        return total_price

    def get_comission_merchandise(self,cr,uid,ids,product_id,merchandise_id,context=None):
        u"""comission du type de transport en fonction du trajet"""
        total_price=0
        comission_merchandise=0
        if merchandise_id and product_id:
            data_object_pricelist_item = self.search(cr,uid,[('price_version_id','=',ids),('product_id','=',product_id)])
            if  data_object_pricelist_item:
                object_pricelist_item=self.browse(cr,uid,data_object_pricelist_item[0])
                for line_merchendise_id in object_pricelist_item.item_merchandise_ids:
                    if line_merchendise_id.merchandise_id.id==merchandise_id:
                        comission_merchandise=line_merchendise_id.comission
        return comission_merchandise


    def get_comission_is_fixed(self,cr,uid,ids,product_id,merchandise_id,context=None):
        total_price=0
        comission_is_fixe=False
        if merchandise_id and product_id:
            data_object_pricelist_item = self.search(cr,uid,[('price_version_id','=',ids),('product_id','=',product_id)])
            if  data_object_pricelist_item:
                object_pricelist_item=self.browse(cr,uid,data_object_pricelist_item[0])
                for line_merchendise_id in object_pricelist_item.item_merchandise_ids:
                    if line_merchendise_id.merchandise_id.id==merchandise_id:
                        comission_is_fixe=line_merchendise_id.fixe
        return comission_is_fixe


    def get_comission_fixe(self,cr,uid,ids,product_id,merchandise_id,context=None):
        total_price=0
        comission_fixe=0
        if merchandise_id and product_id:
            data_object_pricelist_item = self.search(cr,uid,[('price_version_id','=',ids),('product_id','=',product_id)])
            if  data_object_pricelist_item:
                object_pricelist_item=self.browse(cr,uid,data_object_pricelist_item[0])
                for line_merchendise_id in object_pricelist_item.item_merchandise_ids:
                    if line_merchendise_id.merchandise_id.id==merchandise_id:
                        comission_fixe=line_merchendise_id.comission_fixe
        return comission_fixe

    def product_id_change(self, cr, uid, ids, product_id, context=None):
        u"""Evènement lors du changement du trajet"""
        if not product_id:
            return {}
        prod = self.pool.get('product.product').browse(cr, uid, product_id) 
        if prod:
            return {'value': {'name': prod.code,'trajet_ok': prod.trajet_ok}}
        return {}
    
    def onchange_fixed_commission_ok(self,cr,uid,ids,fixed_commission_ok,context=None):
        if fixed_commission_ok:
            return {'value': {'percent_commission_ok': False}}
	return {}
        
    def onchange_percent_commission_ok(self,cr,uid,ids,percent_commission_ok,context=None):
        if percent_commission_ok:
            return {'value': {'fixed_commission_ok': False}}
	return {}
    
product_pricelist_item()
