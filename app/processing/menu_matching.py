from app import pd,FuzzyMatcher,translit,io

def remove_stopwords(x):
    '''Function to drop stopwords from text'''
    stoplist = ['здравствуйте','я','мы','буду','будем','давайте','мне','нам',
               'можно','пожалуйста','спасибо','добрый','день','подскажите',
               'будет','еще','вас','вы','тогда','ну','хочу','хотел','хотела',
               'хотим','так','бы','наверное','вот','этот','эти','эта','это',
               'которая','которые','которое','который','которых','вам','ваш',
               'ваша','ваши','вашим','ваших','будьте','добры','все','будут',
               'будет','меня','потом','заказать','например','заказ','сделать','у','ой','а',
# Todo: place обычный in regex and make synonyms to child dishes - which one is the regular?         
               'обычный','обычную','обычные',
                # TODO: Frequent problem with десерт павлова
                'на','десерт'
               ]
    
    x  = [word for word in x.split() if word not in stoplist]
    x = ' '.join(x)
    return x



def menu_preprocessing(nlp,
                       menupath='gs://sw-bucket-1/restaurants/01-maccheroni/menu.csv'):
    # Pre-process
    # Load menu
    menu = pd.read_csv(menupath)

    menu['multiple_present'].fillna(False,inplace=True)
    menu['add_prefix'].fillna(False,inplace=True)

    # Add prefixes
    menu.loc[(menu['add_prefix']==True),'nlp_title']=\
    menu.loc[(menu['add_prefix']==True),'nlp_prefix'] +' '+\
    menu.loc[(menu['add_prefix']==True),'title']
    menu.loc[(menu['add_prefix']==False),'nlp_title']=menu.loc[(menu['add_prefix']==False),'title']

    dishlist=menu['nlp_title']
    dishlist =dishlist.apply(str.lower)
    dishlist =dishlist.apply(str.strip)
    dishlist = pd.Series(dishlist.unique())

    # Init matcher
    matcher = FuzzyMatcher(nlp.vocab)
    for i,l in enumerate(dishlist):
        matcher.add(i, [nlp(l)], kwargs=[{"fuzzy_func": "token_sort",
                                          "flex":len(l.split())//2,
                                          "min_r2":65}])
    return dishlist,matcher

def text_preprocessing(x,dishlist):
    '''Perform preprocessing on text and dishlist'''
    x=x.lower().strip()
    print('Initial:',x,'\n')
    xs=x.split()
    # Clean consequtive duplicates
    x = ' '.join([n for i, n in enumerate(xs) if i==0 or n != xs[i-1]])
    # Drop some noise
    x=x.replace('ё','е').replace(',','').replace('.','')
    dishlist = dishlist.apply(lambda x: x.replace('ё','е').replace('-',' '))
    # Drop stop words
    x = remove_stopwords(x)
    # Transliterate
    x = translit(x, 'ru')
    print('Processed:',x)
    return x,dishlist

def find_matches(x,dishlist,nlp,matcher):
    '''Find matches in the request from menu dishes
    x - request text
    dishlist - list of dishes from the menu
    '''
    print('Looking for matches...')
    doc = nlp(x)
    
    ## Configure matcher - custom rules
    # try fixes - WORKS!!!
    matcher.patterns[44]['kwargs']['fuzzy_func']='simple'
    # long names - partial sort is goooood :)
    matcher.patterns[32]['kwargs']['fuzzy_func']='partial_token_sort'
    matcher.patterns[144]['kwargs']['fuzzy_func']='partial_token_sort'
    
    matcher.patterns[109]['kwargs']['flex']=2
    matcher.patterns[109]['kwargs']['flex']=2
    matcher.patterns[109]['kwargs']['flex']=2
    
    matches = matcher(doc)
    # Process results
    fdf = pd.DataFrame(matches,columns=['match_id','start','end','ratio'])
    fdf['qty']=1

    # Process overlapping phrases
    # Create ranges from boundaries
    rangelist=[]
    for i in range(len(fdf)):
        rangelist.append(range(fdf['start'][i],fdf['end'][i]))
        fdf.loc[i,'dish']=dishlist[fdf.loc[i,'match_id']]
        fdf.loc[i,'fuzz'] = str(doc[fdf.loc[i,'start']:fdf.loc[i,'end']])
    fdf['range']=rangelist
    # Attach dish names

    fdf2=fdf.iloc[0:0] #Initialize empty copy of fdf
    for m in range(len(fdf)):
        current_subset=fdf['range'][m]
    #     print('current subset:',current_subset,' fuzz string: ',fdf['fuzz'][m])
        setmask=[]
        for n in range(len(fdf)):
            # Search sets that overlap with current subset
            setmask.append(len(set(current_subset)\
                               .intersection(fdf['range'][n]))>0)
        # If superset found, select entry which has greatest 
        # fuzzy search ratio
        selection=fdf[setmask].sort_values(by='ratio',ascending=False)
    #     print('Found options/intersections: \n',selection[['ratio','range','dish']],'\n')
        #append the top one by ratio
        fdf2=fdf2.append(selection.iloc[0,])
    fdf = fdf2.drop_duplicates().reset_index(drop=True) # back to fdf
    comm = io.StringIO()
    print('Found {} matches!'.format(len(fdf)),file=comm)
    return doc,fdf,comm.getvalue()

def print_result(x,doc,dishlist,fdf):
    '''Print out matching result'''
    a = io.StringIO()
    b = io.StringIO()
    print('Order: ',x,'\n',file=a)
    # Assign quantities
    for token in doc:
        if token.like_num:
            print('Token: {} | Head: {} | Head id: {} | Dep: {}'\
                  .format(token.text,
                          token.head.text,
                          token.head.i,
                          token.dep_,))
            for r in range(len(fdf)):
                if token.head.i in fdf.loc[r,'range']:
                    fdf.loc[r,'qty']=token.text

    for i in range(len(fdf)):
        print('Dish: {} | qty: {}'\
              .format(dishlist[fdf.loc[i,'match_id']],fdf.loc[i,'qty']),file=b)
    print('\n')
    return str(a.getvalue() + b.getvalue())