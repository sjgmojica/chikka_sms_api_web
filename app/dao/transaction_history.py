'''
transaction history DAO
@author: vincent agudelo

'''
import traceback, sys

from datetime import datetime


class TransactionHistoryMySQL( object ):
    
    sql_tool = None
    
    code_prefix = '29290'
    
    mt_logs_table_name = 'mt_logs_new'
    mo_logs_table_name = 'mo_logs_new'
    
    
    
    def __init__(self, sql_tool):
        
        self.sql_tool = sql_tool
        
    def get_mo_logs(self, client_id, from_datetime=None, to_datetime=None, items_per_page=None, page_number=None, mobile_filter=None , extra_row=0):
        '''
        @param client_id: api client id used by user to receive mo
        @param from_datetime: Datetime . describes start, usually current datetime
        @param to_datetime: Datetime . describes end, usually current datetime 
        @param limit: Integer . max items returened
        @param mobile_filter: optionally filter query to a specific mobile number 
        
        
        @param extra_row: Integer . used to get next row to see if next page exists 
        
        '''

        logs = []
        
        limit = items_per_page + extra_row


        order_by=['date_sent DESC', 'time_sent DESC']
        #order='DESC'
        
        offset = 0
        if page_number :
            offset = (page_number-1)* items_per_page

        if not client_id:
            return logs
        
        conditions = {
                      'client_id' : client_id
                      }
        
        sender_condition = ''
        if mobile_filter :
             conditions['mobile_number'] = mobile_filter
             sender_condition = '&& `mobile_number`="%s"' % mobile_filter
        
        table_cols = ['mobile_number', 'mobile_number',  'date_sent', 'time_sent', 'cost' ]
        
        
        if from_datetime and to_datetime:
            
            # because sql tool cannot handle YET multiple conditions for the same field (date sent)
            
            conditions['date_sent'] = ( '>=', from_datetime.strftime('%Y-%m-01') )

            if items_per_page == -1:
                query = """SELECT shortcode,mobile_number,message,date_sent,time_sent,cost 
                FROM %s 
                WHERE date_sent >= "%s"  && date_sent < "%s" %s && client_id="%s"
                ORDER BY date_sent DESC,time_sent DESC""" \
                % ( self.mo_logs_table_name,   from_datetime.strftime('%Y-%m-01'), to_datetime.strftime('%Y-%m-01'), sender_condition, client_id )
            else:
                query = """SELECT shortcode,mobile_number,message,date_sent,time_sent,cost 
                FROM %s 
                WHERE date_sent >= "%s"  && date_sent < "%s" %s && client_id="%s"
                ORDER BY date_sent DESC,time_sent DESC
                LIMIT %s OFFSET %s""" \
                % ( self.mo_logs_table_name,   from_datetime.strftime('%Y-%m-01'), to_datetime.strftime('%Y-%m-01'), sender_condition, client_id , limit, offset)
            items = self.sql_tool.run_query('select', query, dictionary=True, fetchall=True)
            
        else:
            items = self.__select( self.mo_logs_table_name  , table_cols=table_cols, conditions=conditions, limit=limit, orderby=order_by, offset=offset)
            
         
        if items :
            for record in items :
                
                if record['cost'] :
                    formatted_cost = record['cost']
                else:
                     formatted_cost = '0.00'
                
                
                logs.append( { 
                              'from' : record['mobile_number'] , 
                              #'body': record['body'] , 
                              #'trans_id': record['transid'],
                              'date_sent': record['date_sent'],
                              'time_sent': record['time_sent'],
                              #'status': '',
                              'cost': formatted_cost,
                              
                              } 
                             )

        return logs
    
    
    def get_mt_logs(self, client_id, from_datetime=None, to_datetime=None, items_per_page=None, mobile_filter=None, page_number=1, sms_type_filter='all', extra_row=0):
        '''
        extra row is used to get an extra row to determine next page
        
        '''
        
        logs = []


        if not client_id:
            return logs

        offset = 0
        if page_number :
            offset = (page_number-1)* items_per_page

        limit = items_per_page+extra_row


        order_by = ['date_received DESC', 'time_received DESC' ]
        table_cols= [ 'date_received', 'time_received', 'mobile_number', 'status', 'credits_cost' , 'message_type', 'rb_credits_cost' ]
        
        if from_datetime and to_datetime :
            my_where = []
            my_where.append('%s="%s"'%('`client_id`',  client_id   ))
            
            if mobile_filter :
                my_where.append(  '%s="%s"' % ('`mobile_number`', mobile_filter)  )
            
            my_where.append(  '%s >= "%s"' % ('`date_received`', from_datetime.strftime('%Y-%m-%d')  ) )
            my_where.append(  '%s < "%s"' % ('`date_received`', to_datetime.strftime('%Y-%m-%d')  ) )

            message_type_filter = ''
            if sms_type_filter =='broadcast':
                my_where.append( "`message_type`='SEND'"    )
            elif sms_type_filter =='reply' :
                my_where.append( "(`message_type`='REPLY_FREE' || `message_type`='REPLY_CHARGED')"    )


            # NOTE !!! @todo
            # Rreverse billoing has tobe computed and summed-up in "cost"

            
            if items_per_page == -1:
                query = """SELECT %s 
                FROM %s 
                WHERE %s 
                ORDER BY %s""" % ( ','.join(table_cols), self.mt_logs_table_name,     ' && '.join(my_where) ,   ','.join(order_by))
            else:
                query = """SELECT %s 
                FROM %s 
                WHERE %s 
                ORDER BY %s  
                LIMIT %s OFFSET %s""" % ( ','.join(table_cols), self.mt_logs_table_name,     ' && '.join(my_where) ,   ','.join(order_by),   limit, offset)

            items = self.sql_tool.run_query( 'select',  query , dictionary=True, fetchall=True )
            # 

            
        else:
            # default setting is current month and current user
            # and ALL message types
            # used on first load of page


            my_where = []
            my_where.append('%s="%s"'%('`client_id`',  client_id   ))
            
            if mobile_filter :
                my_where.append(  '%s="%s"' % ('`mobile_number`', mobile_filter)  )




            if items_per_page == -1:
                query = """SELECT %s 
                FROM %s 
                WHERE %s 
                ORDER BY %s""" % ( ','.join(table_cols), self.mt_logs_table_name,     ' && '.join(my_where) ,   ','.join(order_by))
            else:
                query = """SELECT %s 
                FROM %s 
                WHERE %s 
                ORDER BY %s  
                LIMIT %s OFFSET %s""" % ( ','.join(table_cols), self.mt_logs_table_name,     ' && '.join(my_where) ,   ','.join(order_by),   limit, offset)


            print '------->'
            print query
            print '------->'
            items = self.sql_tool.run_query( 'select',  query , dictionary=True, fetchall=True )
            


            
            #items = self.__select(  self.mt_logs_table_name  ,table_cols=table_cols, limit=limit, conditions=conditions, offset=offset,  orderby=order_by )        
        
        
        
        if items :
            
            for record in items :
                try:
                    formatted_cost = float(record['credits_cost']) + float(record['rb_credits_cost'])
                except:
                    formatted_cost='0.00'
                
                logs.append( { 
                              #'id': record['id'] ,
                              #'message_id' : record['message_id'] ,
                              #'trans_id': record['transid'],
                              #'session_id': record['sessionid'],
                              'receiver' : record['mobile_number'] , 
                              #'sender': record['sender'] , 
                              #'body' : record['body'],
                              'date_received': record['date_received'],
                              'time_received': record['time_received'],
                              'delivery_status' : None,
                              'status': record['status'],
                              'cost' : formatted_cost,
                              'message_type' : self.__transalte_from_db_message_type( message_type=record['message_type'])
                              } 
                             )
        
        return logs

    def __transalte_from_db_message_type(self, message_type):
        '''
        returns the translated message type for website/application purposes
        
        '''
        if message_type == 'SEND':
            in_app_message_type = 'FREE'
        elif message_type == 'REPLY_FREE':
            in_app_message_type = 'PAID'
        elif message_type == 'REPLY_CHARGED':
            in_app_message_type = 'CHARGED'
        else:
            in_app_message_type = None
            
        return in_app_message_type


    def get_mo_total_pages(self, client_id, from_datetime, to_datetime, items_per_page, mobile_filter=None):
        '''
        returns total number of pages for specified date range
        @param client_id: client_id used by to identify the owner of the shortcode
        @param from_datetime: start date range
        @param to_datetime: to date range
        
        @return: non-negative Integer . may return 0 if no records are found
        
        
        sample query (within november) for suffix 925407
        
        SELECT count(id)/9 FROM mo_logs WHERE date_sent > "2013-11-01" && date_sent < "2013-12-01" && receiver="925407"
        
        '''
        if not client_id:
            return logs
                
        mobile_filter_cond = ''
        if mobile_filter:
            mobile_filter_cond = ' && mobile_number = "%s"' % mobile_filter
        
        mo_page_query = """SELECT count(id)/%s as pcount 
        FROM %s 
        WHERE date_sent >= "%s" && date_sent < "%s" && client_id="%s" %s """ % (items_per_page, self.mo_logs_table_name,  from_datetime.strftime('%Y-%m-%d'), to_datetime.strftime('%Y-%m-%d'), client_id, mobile_filter_cond)
        
        return self.__get_total_pages( query=mo_page_query)
        
    def get_mt_total_pages(self, client_id, from_datetime, to_datetime, items_per_page, mobile_filter=None, sms_type_filter='all' ):
        '''
        returns total number of pages for specified date range
        @param client_id: client_id used by to identify the owner of the shortcode
        @param from_datetime: start date range
        @param to_datetime: to date range
        
        @return: non-negative Integer . may return 0 if no records are found
        
        
        sample query (within november) for suffix 925407
        
        SELECT count(id)/9 FROM mt_logs WHERE date_received > "2013-11-01" && date_received < "2013-12-01" && sender="925407"
        
        '''
        if not client_id:
            return logs
        
        mobile_filter_cond = ''
        if mobile_filter:
            mobile_filter_cond = ' && mobile_number = "%s"' % mobile_filter


        message_type_filter_cond = ''
        if sms_type_filter =='broadcast':
            message_type_filter_cond = " && `message_type`='SEND'"
        elif sms_type_filter =='reply' :
            message_type_filter_cond = " && (`message_type`='REPLY_FREE' || `message_type`='REPLY_CHARGED')"


        mt_page_query = """
                        SELECT count(id)/%s as pcount 
                        FROM %s 
                        WHERE date_received >= "%s" && date_received < "%s" && client_id="%s" %s %s"""% ( items_per_page, self.mt_logs_table_name, from_datetime.strftime('%Y-%m-%d'), to_datetime.strftime('%Y-%m-%d'), client_id, mobile_filter_cond, message_type_filter_cond)

        print mt_page_query
        count = self.__get_total_pages( query=mt_page_query)
        print 'counted!!'

        return count


    def __get_total_pages(self, query ):
        
        result = self.sql_tool.run_query( 'select',  query , dictionary=True, fetchall=False )
        
        raw_pcount = float(result['pcount'])


        if raw_pcount == 0:
            return 0

        else :
            
            
            if raw_pcount % 1 :
                total_pages = int(raw_pcount) + 1
            else:
                total_pages = int(raw_pcount)
        
            return total_pages        
  
        
        
    def get_month_sumarry(self, client_id, month=None, year=None ):
        if not client_id:
            return logs
        
        month_sumamry = {}
        
        current_date = datetime.now()
        
        current_month = int(current_date.strftime('%m')) 
        current_year = int(current_date.strftime('%Y'))

        target_month = current_month-2
        
        if current_month < 2 :
            current_year-=1
            target_month = 12 - (2-current_month)
            
        min_date= '%s-%s-01' % (current_year, target_month)
        
        
        
        mo_query = """
            SELECT sum(cost) as cost, count(id) as sms_count, DATE_FORMAT(date_sent, \'%%Y-%%m\') as month_summary, date_format(date_sent, "%%M %%Y") as month_name
            FROM %s
            WHERE `client_id`="%s" && date_sent >= "%s" && cost != "TRIAL"
            GROUP BY month_summary
            ORDER BY date_sent DESC""" % ( self.mo_logs_table_name,  client_id, min_date) ;

        try:
            items = self.sql_tool.run_query( 'select',  mo_query , dictionary=True, fetchall=True )
        except Exception, e:
            raise Exception('unable to fetch monthly summary: %s' % e)
        
        if items :
            for item in items :
                #print item['month_summary']
                month_sumamry[ item['month_summary']  ] = { 'mo' : item } 



        mt_query = 'select sum(credits_cost) as cost, count(id) as sms_count, DATE_FORMAT(date_received, \'%%Y-%%m\') as month_summary, date_format(date_received, "%%M %%Y") as month_name \
        from %s where `client_id`=\'%s\'  && date_received >= "%s"  && credits_cost != "TRIAL"  group by month_summary order by date_received desc' % ( self.mt_logs_table_name, client_id, min_date) ;
        
        try:
            items = self.sql_tool.run_query( 'select',  mt_query , dictionary=True, fetchall=True )
        except Exception, e:
            raise Exception('unable to fetch monthly summary: %s' % e)

        if items :
            for item in items :
                #print item['month_summary']
                if month_sumamry.get( item['month_summary'], None) :
                    month_sumamry[ item['month_summary']  ]['mt'] =  item
                else:
                    month_sumamry[ item['month_summary']  ] = { 'mt' : item }

        
            
            
        
        return month_sumamry
        



    def __select(self, table, table_cols='*', conditions=None, limit=None , orderby=None, order=None, offset=None):
        result = None
        
        try :
            result = self.sql_tool.execute_select(
                                     table_name=table,
                                     table_cols=table_cols,
                                     conditions=conditions,
                                     operator='&&',
                                     limit=limit,
                                     orderby=orderby, order=order,
                                     offset=offset
                                     )
        except Exception, e :
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print traceback.format_tb(exc_traceback)
            raise TransactionHistoryError( 'unable to fetch transaction history: %s' % e )    
            print 'exception rasied ', e
            pass
            
        
        return result


class TransactionHistoryError( Exception ):
    pass        
