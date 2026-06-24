class Registry{
    constructor(){
        this._handlers={};
        this.UFID=0;
    }

    register_handler(op,func,name=undefined){
        let handlerName=name;
        //Create new event hook if not created
        if (!Object.hasOwn(this._handlers,op)){
            this._handlers[op]={};
            console.log(`  Frontend Event Hook ${op} created.`);
        }
        //If name is not provided, replace with _lambda+unique function ID to prevent collision
        if (handlerName===undefined){
            handlerName=`_lambda_${this.UFID}`;
            this.UFID++;
        }
        //Warn if another handler with the same name already exists
        if (Object.hasOwn(this._handlers[op],handlerName)){
            console.warn(`  Handler ${handlerName} already registered under ${op}, overriding!`);
        }
        //Register function in _handlers
        this._handlers[op][handlerName]=func;
        console.log(`  New handler registered under ${op}.`);
    }

    get_handler(op,name=undefined){
        //Return handler if name is provided
        if (name && Object.hasOwn(this._handlers,op)){
            return this._handlers[op][name];
        }
        //Return full dict under event hook(name not provided)
        return this._handlers[op];
    }

    dispatch(op,params,ws,encode){
        const handlers=this.get_handler(op);
        if (handlers){
            for (const key in handlers){
                try{
                    let result=handlers[key](params);
                    //Handlers optionally return a list of messages to send back
                    if (result){
                        for (const msg of result){
                            ws.send(encode(msg));
                        }
                    }
                } catch(e){
                    console.error(`Handler ${handlerName} under ${op} failed:`);
                    console.error(e.message);
                }
            }
        }else{
            console.warn(`Backend attempted to access unknown frontend handler ${op}.`);
        }
    }
}